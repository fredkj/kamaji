# -*- coding: utf-8 -*-
import json

from lettuce import world, step

from shared.lettuce_steps import get_url


@step('I change the password to "(.+)" for "(.+)"')
def i_change_the_password(step, new_password, email):
    result = world.session.post(
        get_url('/auth/password_change/{0}'.format(email)),
        json={
            'token': world.password_reset_token,
            'new_password': new_password
        }
    )

    assert result.status_code == 204


@step('I can authenticate with username "(.+)" and password "(.+)"')
def i_can_authenticate(step, username, password):
    result = world.session.post(get_url('/auth/token/'), json={
        'username': username,
        'password': password
    })

    assert result.status_code == 204


@step('I add user "(.*)" to global group "(.*)"$')
def i_add_user_to_global_group(step, username, global_group_name):
    users_request = world.session.get(get_url('/user_management/users/'))
    users = json.loads(users_request.content)

    matched_user_ids = [user['id'] for user in users
                        if user['username'] == username]

    assert len(matched_user_ids) != 0, \
        'Found no users with username {0}'.format(username)

    groups_request = world.session.get(get_url('/user_management/groups/global/'))
    groups = json.loads(groups_request.content)

    matched_groups = [group for group in groups
                      if group['name'] == global_group_name]

    assert len(matched_groups) == 1, \
        'Found {0} groups matching the name "{1}", 1 match is required'.format(
            len(matched_groups), global_group_name
        )

    group = matched_groups[0]

    group['users'] += matched_user_ids

    url = get_url('/user_management/groups/global/{0}/'.format(group['id']))

    world.response = world.session.put(url, json=group)
