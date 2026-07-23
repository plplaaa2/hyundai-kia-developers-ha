# Hyundai Kia Developers for Home Assistant

[English](README.md) | [한국어](README.ko.md)

![Hyundai Kia Developers](custom_components/hyundai_kia_developers/brand/logo.png)

An unofficial Home Assistant integration for viewing vehicle data from the
Korean Hyundai and Kia developer APIs. It supports multiple accounts and
vehicles, discovers owned vehicles automatically, and renews authorization when
needed.

> This integration supports the Korean developer service only. Accounts,
> projects, and vehicles from other regions are not compatible.

## Requirements

- Home Assistant 2026.7.0 or newer
- HACS
- A Korean Hyundai or Kia developer membership and project
- A vehicle registered to your own Bluelink or Kia Connect account and enabled
  under **My Vehicle** in the developer console

Hyundai and Kia require separate developer memberships and projects. Shared
vehicles may not be available through the developer API.

## Install with HACS

1. In HACS, open **Custom repositories**.
2. Add `https://github.com/mahlernim/hyundai-kia-developers-ha` as an
   **Integration** repository.
3. Install **Hyundai Kia Developers** and restart Home Assistant.

## Prepare the developer project

Follow the [developer-project guide](docs/developer-setup.md) to create the
correct Hyundai or Kia project, obtain its Client ID and Client Secret, register
the redirect URL, and enable your vehicle.

The Account API Redirect URL must be exactly:

```text
https://example.com/redirect
```

## Add an account and vehicle

1. Open **Settings → Devices & services → Add integration** and select
   **Hyundai Kia Developers**.
2. Choose Hyundai or Kia and enter the project credentials.
3. Open the authorization link, sign in with the connected-car account, and
   approve access.
4. When the browser reaches `example.com`, copy the complete address-bar URL
   and paste it into Home Assistant. The page may be blank or show an error;
   the URL is what Home Assistant needs.
5. Select the discovered vehicle and confirm its name.

The redirected URL contains a single-use authorization code. Do not put it in
logs, screenshots, messages, or issues.

## Entities

| Entity | Availability | Default |
| --- | --- | --- |
| Distance to empty | All vehicles | Enabled |
| Odometer | All vehicles | Enabled |
| EV battery level and charging | EV and PHEV | Enabled |
| Combined distance to empty | PHEV, when supplied by the API | Enabled |
| Charging cable, charger type, charge target, and remaining charging time | EV and PHEV | Disabled |
| Fuel, tire, lamp, smart-key battery, washer-fluid, brake-fluid, and engine-oil warnings | When supplied by the vehicle | Disabled |

Disabled entities can be enabled from the vehicle's Home Assistant device page.
Vehicle data is refreshed every 60 minutes by default; the integration options
allow an interval from 30 to 1440 minutes.

## Accounts and vehicles

Account names are generated automatically, for example `Kia`, `Kia 2`, and
`Hyundai`. Use **Add vehicle** on an existing account to add another owned
vehicle. Add a separate account for the other brand.

## Troubleshooting

- **No vehicles found:** Confirm the correct brand account, vehicle ownership,
  active Bluelink or Kia Connect service, and **My Vehicle** activation.
- **The redirect page shows an error:** This is expected. Paste the complete
  URL from the browser address bar into Home Assistant.
- **Authorization expired:** Follow the reauthentication prompt from Home
  Assistant. Use **Reconfigure** only when the Client ID, Client Secret, or
  redirect URL has changed.
- **Error `4002`:** During authorization or token renewal it requires
  reauthorization. During a vehicle update it means that the vehicle request
  was invalid and does not by itself mean the account authorization expired.
- **A value has not changed:** Wait for the next polling interval or reload the
  integration entry.
- **An entity is missing:** Some entities depend on the vehicle type and the
  data made available by the manufacturer.

## Disclaimer and license

This non-profit project is not affiliated with, endorsed by, or sponsored by
Hyundai Motor Company, Kia Corporation, or Home Assistant. Hyundai and Kia names
and related trademarks belong to their respective owners and are used only to
identify API compatibility.

Licensed under the [MIT License](LICENSE).
