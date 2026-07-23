# Prepare a Hyundai or Kia developer project

[English](developer-setup.md) | [한국어](developer-setup.ko.md)

This integration uses the Korean developer service. Hyundai and Kia require
separate memberships and projects.

| Brand | Official guide | Developer console |
| --- | --- | --- |
| Hyundai | [Console guide](https://developers.kia.com/web/v1/hyundai/guide_console) | [console.developers.hyundai.com](https://console.developers.hyundai.com) |
| Kia | [Console guide](https://developers.kia.com/web/v1/kia/guide_console) | [console.developers.kia.com](https://console.developers.kia.com) |

## 1. Prepare the connected-car account

Use the Bluelink or Kia Connect account that owns the vehicle. Shared vehicles
may not appear in the developer console or vehicle list.

If you own vehicles from both brands, complete this guide once for Hyundai and
once for Kia.

## 2. Create the project

1. Join the developer service for the correct brand and sign in to its console.
2. Create a development project and accept the terms shown by the console.
3. Copy the project's **Client ID** and **Client Secret** to a password manager.
4. Set the **Account API Redirect URL** to exactly:

   ```text
   https://example.com/redirect
   ```

   Do not add a trailing slash.

Never commit, post, or screenshot the Client ID, Client Secret, or an OAuth
redirect URL containing an authorization code.

## 3. Enable the vehicle

Open **My Vehicle** in the developer console and activate the vehicle owned by
the connected-car account. If it is absent, confirm the brand account, vehicle
ownership, and active Bluelink or Kia Connect service.

The project is now ready. Return to the [Home Assistant setup](../README.md#add-an-account-and-vehicle).

This project targets personal use with the Korean developer service. API
availability and terms remain under the manufacturer's control.
