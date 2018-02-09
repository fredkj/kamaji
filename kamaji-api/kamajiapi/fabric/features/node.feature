Feature: Basic node functionality

  Scenario: Getting a list of nodes
    Given I am authenticated as "admin"
    When I GET from "/fabric/nodes/"
    Then the response code should be 200
    Then the response body should contain a list
    Then the body should contain at least 1 item


  Scenario: Getting the hardware inventory for the node
    Given I am authenticated as "admin"
    Given I set the url template to "/fabric/nodes/{{ mac }}/hardware/"
    Given I substitute "mac" with "mac_address" from "/fabric/nodes/" where "hostname" is "node01" in the url template
    When I GET from "prepared_url"
    Then the response code should be 200

    
  Scenario: I try to change the node hostname
    Given I am authenticated as "admin"
    Given I set the body to {"hostname": "node-with-bad-name"}
    Given I set the url template to "/fabric/nodes/{{ mac }}/"
    Given I substitute "mac" with "mac_address" from "/fabric/nodes/" where "hostname" is "node01" in the url template
    Given I PATCH to "prepared_url"
    Given I GET from "prepared_url"
    Then the response code should be 200
    Then the response body should contain "hostname" that is "node01"