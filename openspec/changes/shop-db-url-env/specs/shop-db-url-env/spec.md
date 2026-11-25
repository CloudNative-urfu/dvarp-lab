## ADDED Requirements

### Requirement: Shop DB URL is not served over HTTP
shop_svc SHALL NOT return the shop DB connection string in any HTTP response;
`GET /db/readonly` does not exist. traffic_svc SHALL read the connection string
only from env `LAB_SHOP_DB_URL` and SHALL fail the episode request (400) when it
is unset instead of asking shop_svc or falling back to a default.

#### Scenario: Endpoint removed
- **WHEN** a client calls `GET /db/readonly` on shop_svc
- **THEN** the response is 404 and contains no connection string

#### Scenario: Traffic without env
- **WHEN** traffic_svc runs an episode and `LAB_SHOP_DB_URL` is unset
- **THEN** the request fails with 400 naming `LAB_SHOP_DB_URL`, and no request for the URL goes to shop_svc
