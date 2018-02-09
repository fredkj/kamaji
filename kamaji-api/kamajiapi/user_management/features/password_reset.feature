Feature: Perform password reset

  Scenario: Precondition - Create test user
    Given I am authenticated as "admin"
    Given I set the body to:
      """
      {
        ""username": "tester",
        ""first_name": "Test",
        ""last_name": "User",
        ""password": "old_password",
        ""email": "tester@kamaji.io""
      }
      """
    When I POST to "/user_management/users/"

  Scenario: Requesting a password reset
    Given I POST to "/auth/password/change_token_request/tester@kamaji.io"
    Then the response code should be 204

  Scenario: Perform a password change with incorrect token
    Given I set the body to:
    """
    {
      ""token": "thisisnotavalidtoken",
      ""new_token": "n3wp4ssw0rd""
    }
    """
    When I POST to "/auth/password/password_change/tester@kamaji.io"
    Then the response code should be 400

  Scenario: Postcondition - Remote test user
    Given I am authenticated as "admin"
    When I DELETE "/user_management/users/" where "username" is "tester"
