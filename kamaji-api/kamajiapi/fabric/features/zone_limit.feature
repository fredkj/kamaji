Feature: ZoneLimit
  This test assumes there is already one zone configured in the environment.
  Creates 6 zones and asserts the last creation fails because of zone
  limitations.

  Scenario: Create 5 zones
    Given I am authenticated as "admin"
    Given I set the body to {"name": "<name>"}
    When I POST to "/fabric/zones/"
    Then the response code should be 201

  Examples:
    | name |
    | zone-limit-test-1 |
    | zone-limit-test-2 |
    | zone-limit-test-3 |
    | zone-limit-test-4 |
    | zone-limit-test-5 |


  Scenario: Fail to create a seventh zone
    Given I am authenticated as "admin"
    Given I set the body to {"name": "zone.limit-test-6"}
    When I POST to "/fabric/zones/"
    Then the response code should be 400


  Scenario: Delete the 5 zones
    Given I am authenticated as "admin"
    When I DELETE "/fabric/zones/" where "name" is "<name>"
    Then the response code should be 204

  Examples:
    | name |
    | zone-limit-test-1 |
    | zone-limit-test-2 |
    | zone-limit-test-3 |
    | zone-limit-test-4 |
    | zone-limit-test-5 |
