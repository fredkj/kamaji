Feature: Zone Management

  Scenario: Create a zone
    Given I am authenticated as "admin"
    Given I set the body to {"name": "zone-update-test"}
    When I POST to "/fabric/zones/"
    Then the response code should be 201
    Then the response body should contain "name"
    Then the response body should contain "computes" that is "[]"


  Scenario: Remove compute from default-zone
    Given I am authenticated as "admin"
    Given I set the body to {"computes": []}
    When I PATCH "/fabric/zones/" where "name" is "default-zone"
    Then the response code should be 200
    Then the response body should contain "name"
    Then the response body should contain "computes" that is "[]"


  Scenario: Add compute to new zone
    Given I am authenticated as "admin"
    Given I set the body to {"computes": ["node01"]}
    When I PATCH to "/fabric/zones/" where "name" is "zone-update-test"
    Then the response code should be 200
    Then the response body should contain "name"
    Then the response body should contain "computes" that is "[u'node01']"


  Scenario: Remove compute from new zone
    Given I am authenticated as "admin"
    Given I set the body to {"computes": []}
    When I PATCH "/fabric/zones/" where "name" is "zone-update-test"
    Then the response code should be 200
    Then the response body should contain "name"
    Then the response body should contain "computes" that is "[]"


  Scenario: Add compute to default zone
    Given I am authenticated as "admin"
    Given I set the body to {"computes": ["node01"]}
    When I PATCH "/fabric/zones/" where "name" is "default-zone"
    Then the response code should be 200
    Then the response body should contain "name"
    Then the response body should contain "computes" that is "[u'node01']"


  Scenario: Rename a zone
    Given I am authenticated as "admin"
    Given I set the body to {"name": "zone-update-test-renamed"}
    When I PATCH "/fabric/zones/" where "name" is "zone-update-test"
    Then the response code should be 200
    Then the response body should contain "name" that is "zone-update-test-renamed"


  Scenario: Delete the zone
    Given I am authenticated as "admin"
    When I DELETE "/fabric/zones/" where "name" is "zone-update-test-renamed"
    Then the response code should be 204
