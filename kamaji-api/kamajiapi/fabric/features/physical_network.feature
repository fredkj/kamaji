Feature: Creating, getting and deleting a physical network

  Scenario: Creating a physical network
    Given I am authenticated as "admin"
    Given I set the body to:
      """
      {
        ""name": "lettuce-network",
        ""type": "compute_network",
        ""subnet": "192.168.7.64",
        ""prefix": 26,
        ""gateway": "192.168.7.65",
        ""range_start": "192.168.7.110",
        ""range_end": "192.168.7.120""
      }
      """
    When I POST to "/fabric/physicalnetworks/"
    Then the response code should be 201
    Then the response body should contain "name"

  Scenario: Getting the created physical network
    Given I am authenticated as "admin"
    When I GET from "/fabric/physicalnetworks/"
    Then the response code should be 200
    Then the response body should contain a list item where "name" is "lettuce-network"

  Scenario: Deleting a physical network
    Given I am authenticated as "admin"
    When I DELETE "/fabric/physicalnetworks/" where "name" is "lettuce-network"
    Then the response code should be 204
