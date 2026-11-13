import io

import requests


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

        received_response = payload['data']
        all_products.extend(received_response)

        pagination = payload['meta']['pagination']
        if page >= pagination['pageCount'] or not received_response:
            break
        page += 1

    return all_products


def get_product_by_documentid(token, base_url, product_id):
    response = requests.get(
        f'{base_url}/api/products/{product_id}',
        headers={'Authorization': f'Bearer {token}'},
        params={'populate': 'picture'},
    )
    response.raise_for_status()

    return response.json()['data']


def get_product_picture_bytes(product, base_url) -> io.BytesIO:
    picture_url = f"{base_url}{product['picture']['url']}"
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
    payload = {'data': {'tg_user_id': tg_user_id}}

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
    
    return records[0] if records else None


def delete_position(token, base_url, document_id):
    response = requests.delete(
        f'{base_url}/api/positions/{document_id}',
        headers={'Authorization': f'Bearer {token}'},
    )
    response.raise_for_status()


def delete_cart(token, base_url, document_id):
    response = requests.delete(
        f'{base_url}/api/carts/{document_id}',
        headers={'Authorization': f'Bearer {token}'},
    )
    response.raise_for_status()


def delete_user_cart(token, base_url, tg_user_id):
    cart_with_positions = get_cart_with_products(token, base_url, tg_user_id)
    if not cart_with_positions:
        return

    for position in cart_with_positions.get('positions', []):
        delete_position(token, base_url, position['documentId'])

    delete_cart(token, base_url, cart_with_positions['documentId'])


def get_user_by_name(token, base_url, user_name):
    response = requests.get(
        f'{base_url}/api/tg-users',
        headers={'Authorization': f'Bearer {token}'},
        params={'filters[username][$eq]': user_name},
    )
    response.raise_for_status()

    return response.json()['data']


def save_user(token, base_url, user_name, user_email) -> bool:
    """Создаёт пользователя. Возвращает True, если запись создана."""
    if get_user_by_name(token, base_url, user_name):
        return False

    url = f'{base_url}/api/tg-users'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
    payload = {'data': {'username': user_name, 'email': user_email}}

    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()

    return True
