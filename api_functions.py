import io
import os
from pprint import pprint

import requests
from dotenv import load_dotenv


def get_all_products(token, base_url) -> list:
    all_products = []
    page = 1
    page_size = 100

    while True:
        response = requests.get(
            f'{base_url}/api/products',
            headers={'Authorization': f'Bearer {token}'},
            params={
                'pagination[page]': page,
                'pagination[pageSize]': page_size,
            },
        )
        response.raise_for_status()
        payload = response.json()

        recieved_response = payload['data']
        all_products.extend(recieved_response)

        pagination = payload['meta']['pagination']
        if page >= pagination['pageCount'] or not recieved_response:
            break
        page += 1

    return all_products


def get_product_by_documentid(token, base_url, product_id):
    response = requests.get(
        f'{base_url}/api/products/{product_id}',
        headers={'Authorization': f'Bearer {token}'},
        params={
            'populate': 'picture',
        },
    )
    response.raise_for_status()

    return response.json()['data']


def get_product_picture_bytes(product, base_url) -> io.BytesIO:
    picture_url = product['picture']['url']
    picture_url = f'{base_url}{picture_url}'

    response = requests.get(picture_url, stream=True)
    response.raise_for_status()

    picture_bytes = io.BytesIO(response.content)
    picture_bytes.seek(0)

    return picture_bytes


def create_cart(token, base_url, tg_user_id):
    url = f'{base_url}/api/carts'

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }

    payload = {
        'data': {
            'tg_user_id': tg_user_id,
        }
    }

    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()

    return response.json()['data']


def add_product_to_cart(token, base_url, cart_document_id, product_document_id):
    url = f'{base_url}/api/positions'

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }

    payload = {
        'data': {
            'weight': 1,
            'cart': cart_document_id,
            'product': product_document_id,
        }
    }

    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()

    return response.json()['data']


def get_cart_by_user(token, base_url, tg_user_id):
    url = f'{base_url}/api/carts'

    headers = {'Authorization': f'Bearer {token}'}

    params = {'filters[tg_user_id][$eq]': str(tg_user_id)}

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()

    return response.json()['data']


def get_cart_with_products(token, base_url, tg_user_id):
    url = f'{base_url}/api/carts'

    headers = {'Authorization': f'Bearer {token}'}

    params = {
        'filters[tg_user_id][$eq]': str(tg_user_id),
        'populate[positions][populate]': 'product',
    }

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()

    records = response.json()['data']

    if records:
        return records[0]
    return None


def main():
    load_dotenv()
    api_token = os.environ['READ_ONLY_TOKEN']
    host = os.getenv('HOST', 'localhost')
    port = os.getenv('PORT', '1337')

    base_url = f'http://{host}:{port}'

    products = get_all_products(api_token, base_url)

    pprint(products)

    print('\n\n\n')

    product = get_product_by_documentid(api_token, base_url, 8)

    print(product)


if __name__=='__main__':
    main()
