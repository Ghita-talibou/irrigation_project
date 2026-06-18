import base64
import requests

SERVER = "http://157.173.117.156:8080"
CHIRPSTACK_API_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJjaGlycHN0YWNrIiwiZXhwIjoxNzgxNzAwNjM0LCJpc3MiOiJjaGlycHN0YWNrIiwic3ViIjoiMWRjN2I0OGEtY2Q3YS00Yjg1LTljNTMtYzI5NjUzZTgzZGNhIiwidHlwIjoidXNlciJ9.DrR4uD7qhmJfgZFg-WtW8ZGbcWyDNX2DO_HEawpJBDM"
FPORT = 2


def hex_to_base64(payload_hex):
    payload_bytes = bytes.fromhex(payload_hex)
    return base64.b64encode(payload_bytes).decode("utf-8")


def envoyer_downlink_chirpstack(dev_eui, payload_hex):
    if not SERVER or not CHIRPSTACK_API_TOKEN:
        return {
            "success": False,
            "message": "ChirpStack non configuré"
        }

    url = f"{SERVER}/api/devices/{dev_eui}/queue"
    payload_base64 = hex_to_base64(payload_hex)

    headers = {
        "Content-Type": "application/json",
        "Grpc-Metadata-Authorization": f"Bearer {CHIRPSTACK_API_TOKEN}"
    }

    data = {
        "queueItem": {
            "confirmed": False,
            "data": payload_base64,
            "devEui": dev_eui,
            "fPort": FPORT
        }
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=data,
            timeout=10
        )

        if response.status_code in [200, 201, 204]:
            return {
                "success": True,
                "message": "Commande envoyée à ChirpStack"
            }

        return {
            "success": False,
            "message": f"Erreur ChirpStack : {response.status_code} - {response.text}"
        }

    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }