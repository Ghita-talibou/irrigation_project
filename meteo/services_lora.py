import base64
import requests


CHIRPSTACK_API_URL = ""      # à compléter plus tard
CHIRPSTACK_API_TOKEN = ""    # à compléter plus tard
FPORT = 10                   # à confirmer avec le prof


def hex_to_base64(payload_hex):
    payload_bytes = bytes.fromhex(payload_hex)
    return base64.b64encode(payload_bytes).decode("utf-8")


def envoyer_downlink_chirpstack(dev_eui, payload_hex):
    if not CHIRPSTACK_API_URL or not CHIRPSTACK_API_TOKEN:
        return {
            "success": False,
            "message": "ChirpStack non configuré"
        }

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
            CHIRPSTACK_API_URL,
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