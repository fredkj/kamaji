Feature: Zone Management
  TODO: Add tests that assigns computes to zones.

  Scenario: Create a zone
    Given I am authenticated as "admin"
    Given I set the body to {"name": "zone-test", "computes": []}
    When I POST to "/fabric/zones/"
    Then the response code should be 201
    Then the response body should contain "name"


  Scenario: I cannot create a zone with the same name
    Given I am authenticated as "admin"
    Given I set the body to {"name": "zone-test", "computes": []}
    When I POST to "/fabric/zones/"
    Then the response code should be 400


  Scenario: I cannot create a zone with a compute that does not exist
    Given I am authenticated as "admin"
    Given I set the body to:
      """
      {
        ""name": "zone-test-fail",
        ""computes": ["non-existing-compute"]
      }
      """
    When I POST to "/fabric/zones/"
    Then the response code should be 400


  Scenario: Create a second zone
    Given I am authenticated as "admin"
    Given I set the body to {"name": "zone-test-2", "computes": []}
    When I POST to "/fabric/zones/"
    Then the response code should be 201
    Then the response body should contain "name"


  Scenario: Get the created zone
    Given I am authenticated as "admin"
    When I GET from "/fabric/zones/"
    Then the response code should be 200
    Then the response body should contain a list item where "name" is "zone-test"


  Scenario: Getting a non-existent zone returns a 404
    Given I am authenticated as "admin"
    When I GET from "/fabric/zones/666"
    Then the response code should be 404


  Scenario: Update the zone
    Given I am authenticated as "admin"
    Given I set the body to {"name": "zone-test-3"}
    When I PATCH "/fabric/zones/" where "name" is "zone-test"
    Then the response code should be 200
    Then the response body should contain "name"


  Scenario: I cannot update a zone to the name of a zone that already exists
    Given I am authenticated as "admin"
    Given I set the body to {"name": "zone-test-3"}
    When I PATCH "/fabric/zones/" where "name" is "zone-test-2"
    Then the response code should be 400
    Then the response body should contain "name"


  Scenario: Delete the zone
    Given I am authenticated as "admin"
    When I DELETE "/fabric/zones/" where "name" is "zone-test-3"
    Then the response code should be 204


  Scenario: Delete a second zone
    Given I am authenticated as "admin"
    When I DELETE "/fabric/zones/" where "name" is "zone-test-2"
    Then the response code should be 204


  Scenario: Assert I get 400 when trying to create a zone with åäö in its name
    Given I am authenticated as "admin"
    Given I set the body to {"name": "zone-åäö", "computes": []}
    When I POST to "/fabric/zones/"
    Then the response code should be 400

  Scenario: I cannot create a zone with no name
    Given I am authenticated as "admin"
    Given I set the body to {"computes": []}
    When I POST to "/fabric/zones/"
    Then the response code should be 400