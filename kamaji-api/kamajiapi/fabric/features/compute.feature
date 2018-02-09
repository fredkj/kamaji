Feature: Basic compute functionality

  Scenario: Getting a list of computes
    Given I am authenticated as "admin"
    When I GET from "/fabric/computes/"
    Then the response code should be 200
    Then the response body should contain a list
