@storage
Feature: There can only be one CEPH cluster

  Scenario: Verify that you can only have a single CEPH cluster
    Given I am authenticated as "admin"
    Given I set the body to:
      """
      {
        ""name": "test-ceph",
        ""cephx": true,
        ""fsid": "6e56ece4-905f-11e6-8e87-fbc3591081d0",
        ""mon_host": "192.168.7.13",
        ""username": "admin",
        ""password": "AQAedNlWinhLMxAAtWxWlZ+hoN8FegJiFMZFfw==""
      }
      """
      When I POST to "/fabric/external_storage/ceph/"
      Then the response code should be 422


    Scenario: Test CEPH Cluster
    Given I am authenticated as "admin"
    Given I set the body to {"action": "test"}
    When I POST to "/fabric/external_storage/ceph/ceph/action/"
    Then the response code should be 200
    Then the response body should contain "status" that is "connected"
