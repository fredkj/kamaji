# -*- coding: utf-8 -*-
import logging
import os
import sys
import json
from ast import literal_eval
from jinja2 import Template

from django.conf import settings
import requests
import time
from lettuce import world, step
from lettuce.terrain import before

from fabric.features.virtual_machine import VirtualMachineCollection

logger = logging.getLogger(__name__)

# The path to where test resources reside.
RESOURCES_PATH = 'fabric/features/resources'


# Node waiting times in seconds
MAXIMUM_NODE_WAIT_TIME = 7 * 60
NODE_POLLING_INTERVAL = 30

# Test environment
ENVIRONMENT = 'ci01'


DEBUG_TESTS = False

HEADERS = {"Content-Type": "application/json"}


def get_url(resource):
    """
    Gets the url of the api being tested and appends the resource path.
    :param resource: Resource url to append.
    :return: full url of resource.
    """
    if resource == 'prepared_url':
        return settings.INTEGRATION_TEST_URL + world.prepared_url
    else:
        return settings.INTEGRATION_TEST_URL + resource


@before.all
def init_session():
    if sys.flags.optimize:
        raise Exception("Optimizations must be turned off or assertions won't "
                        "be executed.")
    world.session = requests.Session()


@before.each_scenario
def setup_scenario(scenario):
    world.body = {}
    world.files = {}
    world.ids = {}
    world.session.headers = HEADERS.copy()


@step(r'I set the body to (.*)')
def i_set_body_to(step, body):
    world.body = json.loads(body)


@step(r'I set the body to:')
def i_set_body_to_multiline(step):
    body = step.multiline.replace('\n', '')
    world.body = json.loads(body)


@step(r'I add param "(.*)" with value "(.*)" to body$')
def i_add_param_to_body(step, name, value):
    try:
        # Evaluate the value to be able to pass it in as a list, dict, etc...
        # Don't use this in production!
        value = literal_eval(value)
    except ValueError:
        pass
    world.body[name] = value


@step(r'I add param "(.*)" with id where "(.*)" is "(.*)" from "(.*)" in a list to body')
def i_add_param_in_list_to_body(step, field_name, target_key, target_value, url):
    resource = _get_resource(url, target_key, target_value)
    world.body[field_name] = [resource['id']]


@step(
    r'I set the body param "(.*)" to "(.*)" of "(.*)" '
    r'where "(.*)" is "(.*)"'
)
def i_set_body_param_where(
        step,
        target_key,
        source_key,
        url,
        condition_key,
        condition_value):
    world.response = world.session.get(get_url(url))
    logger.debug(world.response.content)
    content = json.loads(world.response.content)
    match = [
        item for item in content
        if condition_key in item
        and item[condition_key] == condition_value
    ]
    assert len(match) > 0
    world.body[target_key] = match[0][source_key]


@step(
    r'I set the body param "(.*)" to list of "(.*)" of "(.*)" where '
    r'"(.*)" is "(.*)"'
)
def i_set_body_param(
        step,
        target_key,
        source_key, url,
        condition_key,
        condition_value):
    world.response = world.session.get(get_url(url))

    logger.debug(world.response.content)
    content = json.loads(world.response.content)

    logger.debug(content)

    match = [
        item for item in content
        if condition_key in item
        and item[condition_key] == condition_value
    ]

    assert len(match) > 0, 'No item where "{0}" is "{1}" in {2}'.format(
        condition_key,
        condition_value,
        url
    )

    world.body[target_key] = [x[source_key] for x in match]


@step(r'I set the files to "(.*)"')
def i_set_files_to(step, filename):
    path = os.path.join(os.getcwd(), RESOURCES_PATH, filename)
    world.files = {
        'file':  open(path, 'rb')
    }


@step(r'I POST to sub-endpoint "(.*)" with (.*) of item nr (.*) of "(.*)"')
def i_post_to_subendpoint(step, sub_endpoint, key, index, endpoint):
    index = int(index)
    url = get_url(endpoint)
    resources = json.loads(world.session.get(url).content)

    sub_endpoint_url = get_url('{0}{1}/'.format(endpoint, '/'.join((
        resources[index][key],
        sub_endpoint))
    ))

    world.response = world.session.post(sub_endpoint_url, world.body)


@step(r'I PUT to resource nr (.*) at "(.*)" with param "(.*)"')
def i_put_to_resource(step, index, resource, param):
    index = int(index)
    url = get_url(resource)
    resources = world.session.get(url)
    body = json.loads(resources.content)
    assert len(body) > index
    world.resource_url = '{0}{1}/'.format(url, body[index][param])

    world.response = world.session.put(world.resource_url, world.body)


@step(r'I GET from resource nr (.*) at "(.*)" with param "(.*)"')
def i_get_from_resource(step, index, resource, param):
    index = int(index)
    url = get_url(resource)
    resources = world.session.get(url)
    body = json.loads(resources.content)
    assert len(body) > index
    resource_url = '{0}{1}/'.format(url, body[index][param])
    world.response = world.session.get(resource_url)


def _get_resource(url, key, value):
    response = world.session.get(get_url(url))
    content = json.loads(response.content)
    match = [x for x in content if key in x and x[key] == value]

    assert len(match) > 0, 'No item where "{0}" is "{1}" at {2}'.format(
        key,
        value,
        url
    )

    return match[0]


def _get_resource_url(url, key, value):
    resource = _get_resource(url, key, value)
    return '{0}{1}/'.format(get_url(url), str(resource['id']))


@step(r'I (POST|GET|PUT|PATCH|DELETE) (to |from |)"(.*)" where "(.*)" is "(.*)"$')
def i_request_where(step, method, _, url, key, value):
    world.resource_url = _get_resource_url(url, key, value)

    data_less_requests = ['GET', 'DELETE']

    if method in data_less_requests:
        world.response = world.session.request(method, world.resource_url)
    else:
        world.response = world.session.request(
            method,
            world.resource_url,
            json=world.body,
            files=world.files
        )


@step(r'I (PATCH|PUT|POST) to "(.*)" where "(.*)" is "(.*)" with plain data$')
def i_patch_where(step, method, url, key, value):
    world.resource_url = _get_resource(url, key, value)

    # Pop the Content type to fall back to defaults
    world.session.headers.pop("Content-Type")

    world.response = world.session.request(
        method,
        world.resource_url,
        world.body,
        files=world.files
    )

    world.files = {}

    # Restore the json content type header
    for key, value in HEADERS.items():
        world.session.headers[key] = value


@step(r'I (POST|PUT|PATCH) to "(.*)" with plain data$')
def i_request_plain(step, method, url):
    # Pop the Content type to fall back to defaults
    world.session.headers.pop("Content-Type")

    world.resource_url = get_url(url)

    world.response = world.session.request(
        method,
        world.resource_url,
        data=world.body,
        files=world.files
    )

    world.files = {}

    # Restore the json content type header
    for key, value in HEADERS.items():
        world.session.headers[key] = value


@step(r'I (POST|GET|PUT|PATCH|DELETE) (to |from |)"(.*)"$')
def i_request(step, method, _, url):
    world.resource_url = get_url(url)
    data_less_requests = ['GET', 'DELETE']

    if method in data_less_requests:
        world.response = world.session.request(method, world.resource_url)
    else:
        world.response = world.session.request(
            method,
            world.resource_url,
            json=world.body,
            files=world.files
        )


@step(r'the response code should be (\d+)$')
def response_code_should_be(step, expected_status_code):
    assert int(expected_status_code) == int(world.response.status_code), \
        "Expected status code {0} but got {1}: {2}".format(
            expected_status_code,
            world.response.status_code,
            world.response.content
        )


@step(r'the response body should contain a list "(.*)" with the id from "(.*)" where "(.*)" is "(.*)"$')
def response_body_should_contain_list_containing_the_id(step, source_key, url, key, value):
    resource = _get_resource(url, key, value)
    assert resource['id'] in world.body[source_key], \
        "Value {0} is not found in field {1}".format(value, key)


@step(r'the response body should contain "([^"]*)" that (is|is not) "(.*)"$')
def response_body_should_contain_where(step, key, equal_or_not, value):
    body = json.loads(world.response.content)
    compare_equality = equal_or_not == 'is'

    # Evaluate the value to make it comparable with {}, [] and None
    # Don't use this in production!
    try:
        value = literal_eval(value)
    except (ValueError, SyntaxError):
        # If a value could not be evaluated, try evaluating it as a string.
        value = literal_eval('"{0}"'.format(value))

    assert key in body, \
        "Key {0} is not present in {1}".format(
            key,
            json.loads(world.response.content)
        )
    assert (body[key] == value) == compare_equality, \
        "Expected key {0} to {1} to {2} but was {3}".format(
            key,
            'be equal' if compare_equality else 'not be equal',
            body[key],
            value
        )


@step(r'the response body should contain a list$')
def response_body_should_contain_a_list(step):
    content = json.loads(world.response.content)
    assert isinstance(content, list)


@step(r'the body should contain (\d+) item(s)?')
def list_should_contain_exact(step, count, plural):
    body = json.loads(world.response.content)
    assert len(body) == int(count)


@step(r'the body should contain at least (.*) item(s)?')
def list_should_contain_at_least(step, count, plural):
    body = json.loads(world.response.content)
    assert len(body) >= int(count)


@step(r'the response body should contain a list item where "([^"]*)" is "(.*)"$')
def response_body_should_contain_list_item(step, key, value):
    content = json.loads(world.response.content)
    match = [x for x in content if key in x and x[key] == value]
    assert len(match) > 0


@step(r'the response body should contain "([^"]*)"$')
def response_body_should_contain(step, key):
    assert key in json.loads(world.response.content), \
        "Key {} is not present in {}".format(
            key,
            json.loads(world.response.content)
        )


@step(r'I am authenticated as "(.*)"')
def _authenticate_as(step, username_and_password):
    world.session.headers = HEADERS.copy()
    response = world.session.post(
        get_url('/auth/token/'),
        json={
            'username': username_and_password,
            'password': username_and_password
        }
    )
    assert response.status_code == 200, \
        'Could not authenticate as {0}, status: {1}, content: {2}'.format(
            username_and_password,
            world.response.status_code,
            world.response.text
        )

    json_response = response.json()
    header = {'Authorization': 'JWT {0}'.format(json_response['token'])}
    world.session.headers.update(header)
    world.body = {}


@step(r'I set the url template to "(.*)"')
def set_prepared_url(step, url_template):
    world.prepared_url = url_template


@step(r'I substitute "(.*)" with "(.*)" from "(.*)" where "(.*)" is "(.*)" in the url template$')
def set_prepared_url_where(step, template_key, url_key, url, key, value):
    resource = _get_resource(url, key, value)
    substitutions = {template_key: resource[url_key]}
    world.prepared_url = Template(world.prepared_url).render(
        **substitutions
    )


@step("I make an unregistered node available")
def make_node_available(step):
    """Restarts the nodes and waits for them to come online."""
    vm = VirtualMachineCollection(ENVIRONMENT)

    vm.restart()

    # Wait a while for the compute to register itself.
    time.sleep(15)

    nodes = json.loads(world.session.get(get_url('/fabric/nodes/')).content)
    waited_time = 0
    while len(nodes) == 0 and waited_time < MAXIMUM_NODE_WAIT_TIME:
        time.sleep(NODE_POLLING_INTERVAL)
        waited_time += NODE_POLLING_INTERVAL
        nodes = json.loads(
            world.session.get(get_url('/fabric/nodes/')).content)
    assert len(nodes) > 0, 'Could not make the compute available'


@step('param "(.*)" should eventually become "(.*)"')
def wait_for_param_to_become(step, watch_param, watch_value):
    timeout = 10 * 60

    start_time = time.time()

    while True:
        response = world.session.get(world.resource_url)
        resource = json.loads(response.content)

        if resource[watch_param] == watch_value:
            assert True
            return

        if time.time() - start_time > timeout:
            logger.fatal('Timed out waiting for {0} to become {1}'.format(
                watch_param,
                watch_value
            ))
            assert False

        time.sleep(5)


@step('"(.*)" should eventually contain a resource where "(.*)" is "(.*)"')
def wait_for_resource_to_become(step, url, key, value):
    timeout = 10 * 60
    start_time = time.time()

    while time.time() - start_time < timeout:
        response = world.session.get(get_url(url))
        content = json.loads(response.content)
        match = [x for x in content if key in x and x[key] == value]

        if match:
            logger.debug('Found resource at {0} where {1} is {2} after {3} sec'
                         .format(url, key, value, time.time() - start_time))
            assert True
            return

        time.sleep(5)

    assert False, 'Timed out waiting for {0} to contain a resource ' \
                  'where {1} is {2}'.format(url, key, value)
