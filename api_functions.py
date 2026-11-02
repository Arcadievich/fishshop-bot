import os
from pprint import pprint

import requests
from dotenv import load_dotenv


def get_all_products(token, base_url):
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


def main():
    load_dotenv()
    api_token = os.environ['READ_ONLY_TOKEN']
    host = os.getenv('HOST', 'localhost')
    port = os.getenv('PORT', '1337')

    base_url = f'http://{host}:{port}'

    products = get_all_products(api_token, base_url)

    pprint(products)


if __name__=='__main__':
    main()
