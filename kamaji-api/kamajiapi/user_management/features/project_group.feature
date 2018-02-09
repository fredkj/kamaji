Feature: Creating, Getting, Patching and Deleting a project group
  Creates a project group, gets it, patches it then deletes it.

  Scenario: Create project
    Given I am authenticated as "admin"
    Given I set the body to:
      """
      {
        ""name": "i_project",
        ""description": "Test project for project group integration tests.",
        ""enabled": "True""
      }
      """
    When I POST to "/projects/"
    Then the response code should be 201


  Scenario: Getting a project group
    Given I am authenticated as "admin"
    When I GET from "/user_management/groups/project/" where "name" is "i_project-project_administrators"
    Then the response code should be 200
    Then the response body should contain "name" that is "i_project-project_administrators"
    Then the response body should contain "project" that is "i_project"
    Then the response body should contain "role" that is "project_administrator"


  Scenario: Patching a project group
    Given I am authenticated as "admin"
    Given I add param "users" with id where "username" is "admin" from "/user_management/users/" in a list to body
    When I PATCH "/user_management/groups/project/" where "name" is "i_project-project_administrators"
    Then the response code should be 200
    Then the response body should contain a list "users" with the id from "/user_management/users/" where "username" is "admin"
    Then the response body should contain "project" that is "i_project"
    Then the response body should contain "role" that is "project_administrator"


  Scenario: Remove project
    Given I am authenticated as "admin"
    When I DELETE "/projects/" where "name" is "i_project"
    Then the response code should be 204
