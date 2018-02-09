Feature: Getting a controller
  
  Scenario: Getting the controller list with the new controller
    Given I am authenticated as "admin"
    When I GET from "/fabric/controllers/"
    Then the response code should be 200
	Then the response body should contain a list item where "name" is "controller01"'


  Scenario: Getting the controller
    Given I am authenticated as "admin"
    When I GET from "/fabric/controllers/" where "name" is "controller01"
    Then the response body should contain "primary"
    Then the response body should contain "ip_address"
    Then the response body should contain "hardware_inventory"
    Then the response code should be 200
