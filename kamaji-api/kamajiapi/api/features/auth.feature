Feature: Auth

  Scenario: Retrieving a token
    Given I set the body to {"username": "admin", "password": "admin"}
    When I POST to "/auth/token/"
    Then the response code should be 200
    Then the response body should contain "token"