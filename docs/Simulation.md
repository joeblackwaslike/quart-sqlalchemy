# Simulation Docs

# initialize database
```shell
quart db create
```
```
Initialized database schema for <QuartSQLAlchemy sqlite:///file:sim.db?cache=shared&uri=true>
```

# add first client to the database (Using CLI)
```shell
quart auth add-client
```
```
Created client 2VolejRejNmG with public_api_key: 5f794cf72d0cef2dd008be2c0b7a632b
```

Use the `public_api_key` returned for the value of the `X-Public-API-Key` header when making API requests.


# Create new auth_user via api
```shell
curl -X POST localhost:8081/api/auth_user/ \
    -H 'X-Public-API-Key: 5f794cf72d0cef2dd008be2c0b7a632b' \
    -H 'Content-Type: application/json' \
    --data '{"email": "joe2@joe.com"}'
```
```json
{
  "data": {
    "auth_user": {
      "client_id": "2VolejRejNmG",
      "current_session_token": "69ee9af5b9296a09f90be5b71c1dda38",
      "date_verified": 1681344793,
      "delegated_identity_pool_id": null,
      "delegated_user_id": null,
      "email": "joe2@joe.com",
      "global_auth_user_id": null,
      "id": "GWpmbk5ezJn4",
      "is_admin": false,
      "linked_primary_auth_user_id": null,
      "phone_number": null,
      "provenance": null,
      "user_type": 2
    }
  },
  "error_code": "",
  "message": "",
  "status": ""
}
```

Use the `current_session_token` returned for the value of `Authorization: Bearer {token}` header when making API Requests requiring a user.

# get AuthUser corresponding to provided bearer session token
```shell
curl -X GET localhost:8081/api/auth_user/ \
    -H 'X-Public-API-Key: 5f794cf72d0cef2dd008be2c0b7a632b' \
    -H 'Authorization: Bearer 69ee9af5b9296a09f90be5b71c1dda38' \
    -H 'Content-Type: application/json' 
```
```json
{
  "data": {
    "client_id": "2VolejRejNmG",
    "current_session_token": "69ee9af5b9296a09f90be5b71c1dda38",
    "date_verified": 1681344793,
    "delegated_identity_pool_id": null,
    "delegated_user_id": null,
    "email": "joe2@joe.com",
    "global_auth_user_id": null,
    "id": "GWpmbk5ezJn4",
    "is_admin": false,
    "linked_primary_auth_user_id": null,
    "phone_number": null,
    "provenance": null,
    "user_type": 2
  },
  "error_code": "",
  "message": "",
  "status": ""
}
```


# AuthWallet Sync
```shell
curl -X POST localhost:8081/api/auth_wallet/sync \
    -H 'X-Public-API-Key: 5f794cf72d0cef2dd008be2c0b7a632b' \
    -H 'Authorization: Bearer 69ee9af5b9296a09f90be5b71c1dda38' \
    -H 'Content-Type: application/json' \
    --data '{"public_address": "xxx", "encrypted_private_address": "xxx", "wallet_type": "ETH"}'
```
```json
{
  "data": {
    "auth_user_id": "GWpmbk5ezJn4",
    "encrypted_private_address": "xxx",
    "public_address": "xxx",
    "wallet_id": "GWpmbk5ezJn4",
    "wallet_type": "ETH"
  },
  "error_code": "",
  "message": "",
  "status": ""
}
```

# get magic client corresponding to provided public api key
```shell
curl -X GET localhost:8081/api/magic_client/ \
    -H 'X-Public-API-Key: 5f794cf72d0cef2dd008be2c0b7a632b' \
    -H 'Content-Type: application/json' 
```
```json
{
  "data": {
    "app_name": "My App",
    "connect_interop": null,
    "global_audience_enabled": false,
    "id": "2VolejRejNmG",
    "is_signing_modal_enabled": false,
    "public_api_key": "5f794cf72d0cef2dd008be2c0b7a632b",
    "rate_limit_tier": null,
    "secret_api_key": "c6ecbced505b35505751c862ed0fb10ffb623d24095019433e0d4d94e240e508"
  },
  "error_code": "",
  "message": "",
  "status": ""
}
```

# Create new magic client
```shell
curl -X POST localhost:8081/api/magic_client/ \
    -H 'X-Public-API-Key: 5f794cf72d0cef2dd008be2c0b7a632b' \
    -H 'Content-Type: application/json' \
    --data '{"app_name": "New App"}'
```
```json
{
  "data": {
    "magic_client": {
      "app_name": "New App",
      "connect_interop": null,
      "global_audience_enabled": false,
      "id": "GWpmbk5ezJn4",
      "is_signing_modal_enabled": false,
      "public_api_key": "fb7e0466e2e09387b93af7da49bb1386",
      "rate_limit_tier": null,
      "secret_api_key": "2ac56a6068d0d4b2ce911ba08401c7bf4acdb03db957550c260bd317c6c49a76"
    }
  },
  "error_code": "",
  "message": "",
  "status": ""
}
```