Feature: URL query parameter filtering
  Scenario: Precondition - Create test user 1
    Given I am authenticated as "admin"
    Given I set the body to:
      """
      {
        ""username": "testuser1",
        ""first_name": "Test",
        ""last_name": "User",
        ""password": "test1",
        ""email": "testuser1@kamaji.io""
      }
      """
    Then I POST to "/user_management/users/"

  Scenario: Precondition - Create test user 2
    Given I am authenticated as "admin"
    Given I set the body to:
      """
      {
        ""username": "testuser2",
        ""first_name": "Test",
        ""last_name": "Userson",
        ""password": "test2",
        ""email": "testuser2@kamaji.io""
      }
      """
    Then I POST to "/user_management/users/"

  Scenario: Precondition - Create test user 3
    Given I am authenticated as "admin"
    Given I set the body to:
      """
      {
        ""username": "testuser3",
        ""first_name": "Testing",
        ""last_name": "User",
        ""password": "test3",
        ""email": "testuser3@kamaji.io""
      }
      """
    Then I POST to "/user_management/users/"
    
  Scenario: Filter on first name
    Given I am authenticated as "admin"
    When I GET from "/user_management/users/?first_name=Test"
    Then the body should contain 2 items

  Scenario: Filter on multiple items
    Given I am authenticated as "admin"
    When I GET from "/user_management/users/?first_name=Test&last_name=Userson"
    Then the body should contain 1 items

  Scenario: Filter on a missing field
    Given I am authenticated as "admin"
    When I GET from "/user_management/users/?linkedin=testerson"
    Then the response code should be 400

  Scenario: Filter on one existing and one missing field
    Given I am authenticated as "admin"
    When I GET from "/user_management/users/?username=testuser2&linkedin=testerson"
    Then the response code should be 400

  Scenario: Postcondition - Remote test user 1
    Given I am authenticated as "admin"
    When I DELETE "/user_management/users/" where "username" is "testuser1"

  Scenario: Postcondition - Remote test user 2
    Given I am authenticated as "admin"
    When I DELETE "/user_management/users/" where "username" is "testuser2"


  Scenario: Postcondition - Remote test user 3
    Given I am authenticated as "admin"
    When I DELETE "/user_management/users/" where "username" is "testuser3"