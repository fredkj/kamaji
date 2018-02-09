Feature: User Management

  Scenario: Create a user
    Given I am authenticated as "admin"
    Given I set the body to:
      """
      {
        ""username": "coolboy",
        ""first_name": "Kalle",
        ""last_name": "Kula",
        ""password": "yoblooc",
        ""email": "cool.boy@verynice.swag""
      }
      """
    When I POST to "/user_management/users/"
    Then the response code should be 201
    Then the response body should contain "username"

  Scenario: Get the created user
    Given I am authenticated as "admin"
    When I GET from "/user_management/users/" where "username" is "coolboy"
    Then the response code should be 200
    Then the response body should contain "username" that is "'coolboy'"
    Then the response body should contain "first_name" that is "'Kalle'"
    Then the response body should contain "last_name" that is "'Kula'"
    Then the response body should contain "email" that is "'cool.boy@verynice.swag'"
    Then the response body should contain "ssh_key"
    Then the response body should contain "global_role"
    Then the response body should contain "project_roles"


  Scenario: Update the user
    Given I am authenticated as "admin"
    Given I set the body to:
      """
      {
        ""username": "notsocoolboy",
        ""first_name": "Sven",
        ""last_name": "Ingbritt",
        ""email": "sven@ingbrittshest.se",
        ""password": "svenbritt""
      }
      """
    When I PUT to "/user_management/users/" where "username" is "coolboy"
    Then the response code should be 200
    Then the response body should contain "username"

  Scenario: Delete the user
    Given I am authenticated as "admin"
    When I DELETE "/user_management/users/" where "username" is "notsocoolboy"
    Then the response code should be 204
