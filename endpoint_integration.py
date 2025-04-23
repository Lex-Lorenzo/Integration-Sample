from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from os import getenv
from urllib.parse import urlencode
from dotenv import load_dotenv
import httpx
import requests
import hubspot
from hubspot.crm.contacts import ApiException, SimplePublicObjectInputForCreate, SimplePublicObjectInput
import json

app = FastAPI()
templates = Jinja2Templates(directory="templates")
load_dotenv()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/integrate")
def get_hubspot_oauth_url(request: Request):
    params = {
        "client_id": getenv('CLIENT_ID'),
        "redirect_uri": getenv('REDIRECT_URI'),
        "scope": "oauth crm.objects.contacts.read crm.objects.contacts.write crm.schemas.contacts.read crm.schemas.contacts.write",
        "response_type": "code"
    }
    oauth_url = f"https://app.hubspot.com/oauth/authorize?{urlencode(params)}"
    return templates.TemplateResponse(
        "open_in_new_tab.html", {"request": request, "oauth_url": oauth_url}
    )

@app.get("/hubspot/oauth/callback")
async def auth_callback(request: Request, code: str):
    try:
        print(f"Received authorization code: {code}")
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                "https://api.hubapi.com/oauth/v1/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": getenv('CLIENT_ID'),
                    "client_secret": getenv('CLIENT_SECRET'),
                    "redirect_uri": getenv('REDIRECT_URI'),
                    "code": code
                }
            )

            print(f"Token response status: {token_response.status_code}")
            print(f"Token response body: {token_response.text}")

            if token_response.status_code == 200:
                tokens = token_response.json()
                return templates.TemplateResponse(
                    "success.html",
                    {"request": request, "tokens": tokens}
                )
            else:
                error_detail = token_response.json().get("error_description", "Unknown error")
                return templates.TemplateResponse(
                    "error.html",
                    {"request": request, "error": error_detail}
                )
    except Exception as e:
        print(f"Error during token exchange: {str(e)}")
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "error": str(e)}
        )
    
@app.post("/refresh-token")
def refresh_hubspot_token(request: Request, refresh_token: str = Form(...)):
    try:
        print(f"Received refresh token: {refresh_token}")
        url = "https://api.hubapi.com/oauth/v1/token"
        data = {
            "grant_type": "refresh_token",
            "client_id": getenv('CLIENT_ID'),
            "client_secret": getenv('CLIENT_SECRET'),
            "refresh_token": refresh_token
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }

        token_response = requests.post(url, data=data, headers=headers)
        token_response.raise_for_status()
        print(f"Token response status: {token_response.status_code}")
        print(f"Token response body: {token_response.text}")

        if token_response.status_code == 200:
            tokens = token_response.json()
            access_token = tokens.get("access_token")
            # Create the template response
            template_response = templates.TemplateResponse(
                "success.html",
                {"request": request, "tokens": tokens}
            )

            # Set the access_token cookie (HttpOnly)
            template_response.set_cookie(
                key="access_token",
                value=access_token,
                httponly=True,
                secure=True,       # Use only with HTTPS
                samesite="lax",
                max_age=3600       # 1 hour expiration
            )

            return template_response
        else:
            error_detail = token_response.json().get("error_description", "Unknown error")
            return templates.TemplateResponse(
                "error.html",
                {"request": request, "error": error_detail}
            )
    except Exception as e:
        print(f"Error during token exchange: {str(e)}")
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "error": str(e)}
        )
    
@app.get("/contacts", response_class=HTMLResponse)
def return_contacts(request: Request):
    return templates.TemplateResponse("contacts.html", {"request": request})

    
@app.get("/get-all-contacts", response_class=HTMLResponse)
async def get_contacts(request: Request):
    try:
        access_key = request.cookies.get("access_token")
        print(f"Access Key Received: {access_key}")

        url = "https://api.hubapi.com/crm/v3/objects/contacts"
        headers = {
            "authorization": f'Bearer {access_key}',
        }
        params = {
            "limit": 10,
            "archived": "false"
        }

        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        print(f"Response status: {response.status_code}")
        print(f"Response body: {data}")

        return templates.TemplateResponse(
            "all_contacts.html", {"request": request, "contacts": data['results']}
        )
    except Exception as e:
        print(f"Error during contacts retrieval: {str(e)}")
        return templates.TemplateResponse(
            "error.html", {"request": request, "error": str(e)}
        )

@app.post("/get-contact", response_class=HTMLResponse)
async def get_contact_by_id(request: Request, access_key: str = Form(...), contact_id: str = Form(...)):
    try:
        print(f"Access Key Received: {access_key}")
        print(f"Contact ID Received: {contact_id}")

        url = f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}"
        headers = {
            "authorization": f'Bearer {access_key}',
        }
        params = {
            "limit": 10,
            "archived": "false"
        }

        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        print(f"Response status: {response.status_code}")
        print(f"Response body (endpoint_here): {data}")

        return templates.TemplateResponse(
            "contact_detail.html", {"request": request, "contact": data}
        )
    except ApiException as e:
        print(f"Error during contact retrieval: {str(e)}")
        return templates.TemplateResponse(
            "error.html", {"request": request, "error": str(e)}
        )
    
@app.get("/get-contact/{contact_id}", response_class=HTMLResponse)
async def get_contact_by_id(request: Request, contact_id: str):
    try:
        access_key = request.cookies.get("access_token")
        print(f"Access Key Received: {access_key}")
        print(f"Contact ID Received: {contact_id}")

        url = f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}"
        headers = {
            "authorization": f'Bearer {access_key}',
        }
        params = {
            "limit": 10,
            "archived": "false"
        }

        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        print(f"Response status: {response.status_code}")
        print(f"Response body (endpoint_here): {data}")

        return templates.TemplateResponse(
            "contact_detail.html", {"request": request, "contact": data}
        )
    except ApiException as e:
        print(f"Error during contact retrieval: {str(e)}")
        return templates.TemplateResponse(
            "error.html", {"request": request, "error": str(e)}
        )
    
@app.post("/create-contact", response_class=HTMLResponse)
async def create_contact(request: Request):
    try:
        form_data = await request.form()
        access_key = request.cookies.get("access_token")
        properties = {
            "firstname": form_data.get("first_name"),
            "lastname": form_data.get("last_name"),
            "email": form_data.get("email"),
            "phone": form_data.get("phone"),
        }

        print(f"Form Data Received: {properties}")
        print(f"Access Key Received: {access_key}")

        url = "https://api.hubapi.com/crm/v3/objects/contacts"

        headers = {
            "authorization": f'Bearer {access_key}',
            "Content-Type": "application/json"
        }

        data = {
            "properties": {
                "firstname": form_data.get("first_name"),
                "lastname": form_data.get("last_name"),
                "email": form_data.get("email"),
                "phone": form_data.get("phone"),
            }
        }

        response = requests.post(url, headers=headers, json=data)

        return templates.TemplateResponse(
            "contact_detail.html", {"request": request, "contact": response.json()}
        )
    except Exception as e:
        print(f"Error during contacts retrieval: {str(e)}")
        return templates.TemplateResponse(
            "error.html", {"request": request, "error": str(e)}
        )
    
@app.post("/update-contact", response_class=HTMLResponse)
async def create_contact(request: Request):
    try:
        form_data = await request.form()
        access_key = request.cookies.get("access_token")
        contact_id = form_data.get("contact_id")
        print('FORM DATA:', form_data)
        print(f"Access Key Received: {access_key}")

        url = f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}"

        headers = {
            "authorization": f'Bearer {access_key}',
            "Content-Type": "application/json"
        }

        data = {
            "properties": {
                "firstname": form_data.get("first_name"),
                "lastname": form_data.get("last_name"),
                "email": form_data.get("email"),
                "phone": form_data.get("phone"),
            }
        }

        response = requests.patch(url, headers=headers, json=data)
        return templates.TemplateResponse(
            "contact_detail.html", {"request": request, "contact": response.json()}
        )
    except Exception as e:
        print(f"Error during contacts retrieval: {str(e)}")
        return templates.TemplateResponse(
            "error.html", {"request": request, "error": str(e)}
        )
