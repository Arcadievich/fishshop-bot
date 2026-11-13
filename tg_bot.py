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
    save_user,
)

_database = None


def get_main_menu_keyboard(products):
    keyboard = [
        [InlineKeyboardButton(p['title'], callback_data=p['documentId'])]
        for p in products
    ]
    keyboard.append([
        InlineKeyboardButton('Моя корзина', callback_data='show_user_cart')
    ])
    return InlineKeyboardMarkup(keyboard)


def get_product_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('Добавить в корзину', callback_data='add_to_cart')],
        [InlineKeyboardButton('Моя корзина', callback_data='show_user_cart')],
        [InlineKeyboardButton('Назад', callback_data='back_to_menu')],
    ])


def get_empty_cart_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('Назад', callback_data='back_to_menu')],
    ])


def get_full_cart_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('Оплатить', callback_data='get_email')],
        [InlineKeyboardButton('Удалить товар', callback_data='delete_cart')],
        [InlineKeyboardButton('Назад', callback_data='back_to_menu')],
    ])


def safe_delete_message(message):
    try:
        message.delete()
    except Exception:
        pass


def send_menu(chat_id, context):
    """Отправляет главное меню со списком товаров."""
    products = get_all_products(
        context.bot_data['cms_full_access_token'],
        context.bot_data['cms_url'],
    )
    context.bot.send_message(
        chat_id=chat_id,
        text='Выберите товар:',
        reply_markup=get_main_menu_keyboard(products),
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
    context.user_data['chosen_product_document_id'] = product_document_id

    product = get_product_by_documentid(
        context.bot_data['cms_full_access_token'],
        context.bot_data['cms_url'],
        product_document_id,
    )

    safe_delete_message(query.message)

    caption = f"{product['title']}\n\n{product['description']}"

    try:
        picture_bytes = get_product_picture_bytes(
            product, context.bot_data['cms_url']
        )
    except (KeyError, TypeError):
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=caption,
            reply_markup=get_product_keyboard(),
        )
    else:
        context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=picture_bytes,
            caption=caption,
            parse_mode='HTML',
            reply_markup=get_product_keyboard(),
        )

    return 'HANDLE_DESCRIPTION'


def handle_description_buttons(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    if query.data == 'back_to_menu':
        safe_delete_message(query.message)
        return start(update, context)

    if query.data == 'add_to_cart':
        return handle_add_to_cart(update, context)

    if query.data == 'show_user_cart':
        return handle_show_cart(update, context)


def handle_add_to_cart(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = update.effective_chat.id
    product_document_id = context.user_data.get('chosen_product_document_id')

    token = context.bot_data['cms_full_access_token']
    base_url = context.bot_data['cms_url']

    user_carts = get_cart_by_user(token, base_url, user_id)
    if user_carts:
        cart_document_id = user_carts[0]['documentId']
    else:
        new_cart = create_cart(token, base_url, str(user_id))
        cart_document_id = new_cart['documentId']

    add_product_to_cart(token, base_url, cart_document_id, product_document_id)

    safe_delete_message(query.message)
    send_menu(user_id, context)

    return 'HANDLE_MENU'


def build_cart_text_and_keyboard(cart):
    """Собирает текст и клавиатуру корзины."""
    if not cart or not cart.get('positions'):
        return 'Ваша корзина пуста.', get_empty_cart_keyboard()

    lines = ['<b>Ваша корзина:</b>\n']
    total = 0
    for position in cart['positions']:
        product = position['product']
        weight = position['weight']
        price = product['price']
        total += price * weight
        lines.append(f"- {product['title']} — {weight} шт. × {price} руб.")
    lines.append(f'\n<b>Итого: {total} руб.</b>')

    return '\n'.join(lines), get_full_cart_keyboard()


def handle_show_cart(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    cart = get_cart_with_products(
        context.bot_data['cms_full_access_token'],
        context.bot_data['cms_url'],
        update.effective_chat.id,
    )

    safe_delete_message(query.message)

    text, keyboard = build_cart_text_and_keyboard(cart)
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        parse_mode='HTML',
        reply_markup=keyboard,
    )

    return 'HANDLE_CART'


def handle_cart_buttons(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    if query.data == 'get_email':
        safe_delete_message(query.message)
        return handle_email_request(update, context)

    if query.data == 'back_to_menu':
        safe_delete_message(query.message)
        return start(update, context)

    if query.data == 'delete_cart':
        safe_delete_message(query.message)
        return handle_delete_user_cart(update, context)


def handle_delete_user_cart(update: Update, context: CallbackContext):
    delete_user_cart(
        context.bot_data['cms_full_access_token'],
        context.bot_data['cms_url'],
        update.effective_chat.id,
    )

    return start(update, context)


def handle_email_request(update: Update, context: CallbackContext):
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='Пришлите ваш адрес электронной почты для дальнейшей связи '
             'в следующем сообщении',
    )

    return 'WAITING_EMAIL'


def handle_user_email_reply(update: Update, context: CallbackContext):
    token = context.bot_data['cms_full_access_token']
    base_url = context.bot_data['cms_url']
    user_name = update.effective_user.username
    user_email = update.message.text

    is_created = save_user(token, base_url, user_name, user_email)

    if is_created:
        text = 'Спасибо, наш менеджер свяжется с вами по электронной почте'
    else:
        text = 'Вы уже оформляли заказ. Мы свяжемся с вами по указанной почте'

    context.bot.send_message(chat_id=update.effective_chat.id, text=text)

    return start(update, context)


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
        'WAITING_EMAIL': handle_user_email_reply,
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

    tg_token = os.getenv('TG_BOT_TOKEN')
    proxy_url = os.getenv('PROXY_URL')

    updater_kwargs = {'use_context': True}
    if proxy_url:
        updater_kwargs['request_kwargs'] = {'proxy_url': proxy_url}

    updater = Updater(tg_token, **updater_kwargs)
    dispatcher = updater.dispatcher

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