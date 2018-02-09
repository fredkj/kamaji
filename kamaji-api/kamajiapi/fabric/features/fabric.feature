# This test needs some manual steps to be executed before being run.
# 1. Set the default project of the admin used to 'admin'.
# 2. As we haven't figured out how to restart a node yet, this will have to
#    be done manually also, and before that a computenetwork will have to be
#    created with the name default-network.
#
@fabric
Feature: Fabric End-to-End test
  Scenario: Set up CEPH cluster
    Given I am authenticated as "admin"
    Given I set the body to:
    """
    {
      ""name": "ceph",
      ""cephx": true,
      ""fsid": "5f84ff5f-dd4a-42a8-91fb-56658eaf8909",
      ""mon_host": "10.192.5.13",
      ""username": "admin",
      ""password": "AQAedNlWinhLMxAAtWxWlZ+hoN8FegJiFMZFfw==""
    }
    """
    When I POST to "/fabric/external_storage/ceph/"
    Then the response code should be 201


  Scenario Outline: Set up CEPH Pools
    Given I am authenticated as "admin"
    Given I add param "pool" with value "<pool>" to body
    Given I add param "type" with value "<type>" to body
    When I POST to "/fabric/external_storage/ceph/ceph/shares/"
    Then the response code should be 201

  Examples:
    | pool    | type   |
    | volumes | volume |
    | images  | image  |
    | vms     | meta   |


  Scenario: Test CEPH Cluster
    Given I am authenticated as "admin"
    Given I add param "action" with value "test" to body
    When I POST to "/fabric/external_storage/ceph/ceph/action/"
    Then the response code should be 200
    Then the response body should contain "status" that is "connected"


  Scenario: Connect CEPH Cluster
    Given I am authenticated as "admin"
    Given I add param "action" with value "connect" to body
    When I POST to "/fabric/external_storage/ceph/ceph/action/"
    Then the response code should be 200


  Scenario: Create compute network
    Given I am authenticated as "admin"
    Given I set the body to:
    """
    {
      ""name": "compute_network01",
      ""subnet": "10.192.16.0",
      ""gateway": "10.192.16.1",
      ""range_start": "10.192.16.2",
      ""range_end": "10.192.16.62",
      ""type": "compute_network",
      ""prefix": 26
    }
    """
    When I POST to "/fabric/physicalnetworks/"
    Then the response code should be 201
    Then the response body should contain "subnet"


  Scenario: Register Compute
    Given I am authenticated as "admin"
    Given I make an unregistered node available
    Given I set the body to:
      """
      {
        ""hostname": "default-compute",
        ""node_type": "compute",
        ""active": true
      }
      """
    Given I set the body param "ip_address" to "ip_address" of "/fabric/nodes/" where "node_type" is "unconfigured"
    Given I set the body param "mac_address" to "mac_address" of "/fabric/nodes/" where "node_type" is "unconfigured"
    Given I set the body param "prefix" to "prefix" of "/fabric/physicalnetworks/" where "gateway" is "10.192.16.1"
    When I PUT to resource nr 0 at "/fabric/nodes/" with param "mac_address"
    Then param "state" should eventually become "READY"
    Then "/fabric/computes/" should eventually contain a resource where "hostname" is "node01"
