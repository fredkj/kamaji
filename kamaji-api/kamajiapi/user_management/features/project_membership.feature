Feature: Project Membership

  Scenario: Create a user
    Given I am authenticated as "admin"
    Given I set the body to:
      """
      {
        ""username": "zelda",
        ""first_name": "Link",
        ""last_name": "zelda",
        ""password": "zelda",
        ""email": "zelda@castle.swag""
      }
      """
    When I POST to "/user_management/users/"
    Then the response code should be 201
    Then the response body should contain "username"


  Scenario: Add user to default-project as spectator
    Given I am authenticated as "admin"
    Given I set the body to {"role": "project_spectator"}
    Given I set the url template to "/projects/{{ project_id }}/memberships/zelda/"
    Given I substitute "project_id" with "id" from "/projects/" where "name" is "default-project" in the url template
    When I PUT to "prepared_url"
    Then the response code should be 204


  Scenario: Get the user through the project scoped endpoint
    Given I am authenticated as "admin"
    Given I set the url template to "/projects/{{ project_id }}/users/"
    Given I substitute "project_id" with "id" from "/projects/" where "name" is "default-project" in the url template
    When I GET from "prepared_url" where "username" is "zelda"
    Then the response code should be 200
    Then the response body should contain "project_roles" that is "{"default-project": "project_spectator"}"


  Scenario: Delete the user
    Given I am authenticated as "admin"
    When I DELETE "/user_management/users/" where "username" is "zelda"
    Then the response code should be 204
