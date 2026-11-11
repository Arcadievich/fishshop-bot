import os

import redis
from dotenv import load_dotenv
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    Filters,
    MessageHandler,
    Updater,
)

from api_functions import (
    add_product_to_cart,
    create_cart,
    delete_user_cart,
    get_all_products,
    get_cart_by_user,
    get_cart_with_products,
    get_product_by_documentid,
    get_product_picture_bytes,
)

_database = None


def get_main_menu_keyboard(products):
    keyboard = []
    for product in products:
        keyboard.append([
            InlineKeyboardButton(
                product['title'],
                callback_data=product['documentId'],
            )
        ])
    keyboard.append([InlineKeyboardButton('Моя корзина', callback_data='show_user_cart')])
    return InlineKeyboardMarkup(keyboard)


def send_menu(chat_id, context):
    cms_token = context.bot_data.get('cms_read_token')
    cms_url = context.bot_data.get('cms_url')

    products = get_all_products(cms_token, cms_url)
    keyboard = get_main_menu_keyboard(products)

    context.bot.send_message(
        chat_id=chat_id,
        text='Выберите товар:',
        reply_markup=keyboard,
    )


def start(update: Update, context: CallbackContext):
    send_menu(update.effective_chat.id, context)
    return 'HANDLE_MENU'


def press_product_button(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    if query.data == 'show_user_cart':
        return handle_show_cart(update, context)
    if query.data == 'back_to_menu':
        return start(update, context)

    product_document_id = query.data
    context.user_data['choosen_product_document_id'] = product_document_id

    cms_token = context.bot_data.get('cms_read_token')
    cms_url = context.bot_data.get('cms_url')
    product = get_product_by_documentid(cms_token, cms_url, product_document_id)

    try:
        query.message.delete()
    except Exception:
        pass

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton('Добавить в корзину', callback_data='add_to_cart')],
        [InlineKeyboardButton('Моя корзина', callback_data='show_user_cart')],
        [InlineKeyboardButton('Назад', callback_data='back_to_menu')],
    ])

    caption = f"{product['title']}\n\n{product['description']}"

    try:
        picture_bytes = get_product_picture_bytes(product, cms_url)
    except (KeyError, TypeError):
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=caption,
            reply_markup=keyboard,
        )
    else:
        context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=picture_bytes,
            caption=caption,
            parse_mode='HTML',
            reply_markup=keyboard,
        )

    return 'HANDLE_DESCRIPTION'


def handle_add_to_cart(update: Update, context: CallbackContext):
    cms_token = context.bot_data.get('cms_full_access_token')
    cms_url = context.bot_data.get('cms_url')
    user_id = update.effective_chat.id
    product_document_id = context.user_data.get('choosen_product_document_id')

    user_carts = get_cart_by_user(cms_token, cms_url, user_id)

    if user_carts:
        cart_document_id = user_carts[0]['documentId']
    else:
        new_cart = create_cart(cms_token, cms_url, str(user_id))
        cart_document_id = new_cart['documentId']

    add_product_to_cart(
        cms_token,
        cms_url,
        cart_document_id,
        product_document_id,
    )

    try:
        update.callback_query.message.delete()
    except Exception:
        pass

    send_menu(user_id, context)
    return 'HANDLE_MENU'


def handle_show_cart(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    cms_token = context.bot_data.get('cms_full_access_token')
    cms_url = context.bot_data.get('cms_url')
    user_id = update.effective_chat.id

    try:
        query.message.delete()
    except Exception:
        pass

    cart = get_cart_with_products(cms_token, cms_url, user_id)

    if not cart or not cart.get('positions'):
        text = 'Ваша корзина пуста.'
    else:
        lines = ['<b>Ваша корзина:</b>\n']
        total = 0
        for position in cart['positions']:
            product = position['product']
            weight = position['weight']
            price = product['price']
            total += price * weight
            lines.append(f"- {product['title']} — {weight} шт. × {price} руб.")
        lines.append(f'\n<b>Итого: {total} руб.</b>')
        text = '\n'.join(lines)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton('Удалить товар', callback_data='delete_cart')],
        [InlineKeyboardButton('Назад', callback_data='back_to_menu')],
    ])

    context.bot.send_message(
        chat_id=user_id,
        text=text,
        parse_mode='HTML',
        reply_markup=keyboard,
    )

    return 'HANDLE_CART'


def handle_description_buttons(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    if query.data == 'back_to_menu':
        try:
            query.message.delete()
        except Exception:
            pass
        return start(update, context)

    if query.data == 'add_to_cart':
        return handle_add_to_cart(update, context)

    if query.data == 'show_user_cart':
        return handle_show_cart(update, context)


def handle_delete_user_cart(update: Update, context: CallbackContext):
    cms_token = context.bot_data.get('cms_full_access_token')
    cms_url = context.bot_data.get('cms_url')
    user_id = update.effective_chat.id

    delete_user_cart(cms_token, cms_url, user_id)

    return start(update, context)


def handle_cart_buttons(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    if query.data == 'back_to_menu':
        try:
            query.message.delete()
        except Exception:
            pass
        return start(update, context)
    
    if query.data == 'delete_cart':
        try:
            query.message.delete()
        except Exception:
            pass
        return handle_delete_user_cart(update, context)


def handle_users_reply(update, context):
    db = get_database_connection()

    if update.message:
        user_reply = update.message.text
        chat_id = update.message.chat_id
    elif update.callback_query:
        user_reply = update.callback_query.data
        chat_id = update.callback_query.message.chat_id
    else:
        return

    if user_reply == '/start':
        user_state = 'START'
    else:
        state = db.get(chat_id)
        user_state = state.decode('utf-8') if state else 'START'

    states_functions = {
        'START': start,
        'HANDLE_MENU': press_product_button,
        'HANDLE_DESCRIPTION': handle_description_buttons,
        'HANDLE_CART': handle_cart_buttons,
    }

    state_handler = states_functions[user_state]

    try:
        next_state = state_handler(update, context)
        if next_state:
            db.set(chat_id, next_state)
    except Exception as err:
        print(f'Ошибка: {err}')


def get_database_connection():
    global _database
    if _database is None:
        load_dotenv()
        _database = redis.Redis(
            host=os.getenv('DATABASE_HOST'),
            port=os.getenv('DATABASE_PORT'),
            db=os.getenv('DATABASE_NUMBER'),
        )
    return _database


def main():
    load_dotenv()

    updater = Updater(
        os.getenv('TG_BOT_TOKEN'),
        request_kwargs={'proxy_url': 'http://127.0.0.1:2080'},
        use_context=True,
    )
    dispatcher = updater.dispatcher

    dispatcher.bot_data['cms_read_token'] = os.environ['READ_ONLY_TOKEN']
    dispatcher.bot_data['cms_full_access_token'] = os.environ['FULL_ACCESS_TOKEN']
    dispatcher.bot_data['cms_url'] = (
        f"http://{os.getenv('HOST', 'localhost')}:{os.getenv('PORT', '1337')}"
    )

    dispatcher.add_handler(CallbackQueryHandler(handle_users_reply))
    dispatcher.add_handler(MessageHandler(Filters.text, handle_users_reply))
    dispatcher.add_handler(CommandHandler('start', handle_users_reply))

    print('Бот запущен.')
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()