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


def get_product_by_id(token, base_url, product_id):
    response = requests.get(
        f'{base_url}/api/products',
        headers={'Authorization': f'Bearer {token}'},
        params={
            'filters[id][$eq]': product_id,
            'pagination[pageSize]': 1,
            'populate': 'picture',
        },
    )
    response.raise_for_status()

    record = response.json()['data']

    return record[0]


def get_product_picture_bytes(product, base_url) -> io.BytesIO:
    picture_url = product['picture']['url']
    picture_url = f'{base_url}{picture_url}'

    response = requests.get(picture_url, stream=True)
    response.raise_for_status()

    picture_bytes = io.BytesIO(response.content)
    picture_bytes.seek(0)

    return picture_bytes


def main():
    load_dotenv()
    api_token = os.environ['READ_ONLY_TOKEN']
    host = os.getenv('HOST', 'localhost')
    port = os.getenv('PORT', '1337')

    base_url = f'http://{host}:{port}'

    products = get_all_products(api_token, base_url)

    pprint(products)

    print('\n\n\n')

    product = get_product_by_id(api_token, base_url, 8)

    print(product)


if __name__=='__main__':
    main()
