Feature: Basic volume functionality

  Scenario: Test getting empty volumes list
    Given I am authenticated as "admin"
    Given I set the prepared url to "/projects/{0}/volumes/"
    Given I prepare the url with "id" from "/projects/" where "name" is "default-project"
    When I GET from "prepared_url"
    Then the response body should contain a list
    Then the body should contain 0 items

  Scenario: Test getting volume list for missing project
    Given I am authenticated as "admin"
    When I GET from "/projects/4711/volumes"
    Then the response code should be 404

  Scenario: Test getting volume for missing project
    Given I am authenticated as "admin"
    When I GET from "/projects/4711/volumes/1337"
    Then the response code should be 404
