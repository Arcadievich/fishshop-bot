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
    get_all_products,
    get_cart_by_user,
    get_product_by_id,
    get_product_picture_bytes,
)

_database = None


def send_menu(chat_id, context):
    """Отправляет пользователю меню с продуктами."""
    cms_token = context.bot_data.get('cms_read_token')
    cms_url = context.bot_data.get('cms_url')

    products_from_cms = get_all_products(cms_token, cms_url)

    keyboard = []

    for product in products_from_cms:
        keyboard.append([
            InlineKeyboardButton(
                product['title'],
                callback_data=product['documentId'],
            )
        ])

    context.bot.send_message(
        chat_id=chat_id,
        text='Please choose:',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


def start(update: Update, context: CallbackContext):
    send_menu(update.effective_chat.id, context)

    return 'HANDLE_MENU'


def press_product_button(update: Update, context: CallbackContext):
    query = update.callback_query
    old_message = query.message

    cms_read_token = context.bot_data.get('cms_read_token')
    cms_url = context.bot_data.get('cms_url')

    product_document_id = query.data
    context.user_data['choosen_product_document_id'] = product_document_id

    product = get_product_by_id(cms_read_token, cms_url, query.data)

    query.answer()

    try:
        old_message.delete()
    except Exception as e:
        print(f'Не удалось удалить сообщение: {e}')

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton('Добавить в корзину', callback_data='add_to_cart')],
        [InlineKeyboardButton('Назад', callback_data='back_to_menu')],
    ])

    caption_text = f"{product['title']}\n\n{product['description']}"

    try:
        picture_bytes = get_product_picture_bytes(product, cms_url)
    except (KeyError, TypeError):
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=caption_text,
            reply_markup=keyboard,
        )
    else:
        context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=picture_bytes,
            caption=caption_text,
            parse_mode='HTML',
            reply_markup=keyboard,
        )

    return 'HANDLE_DESCRIPTION'


def handle_description_buttons(update: Update, context: CallbackContext):
    """Обрабатывает нажатия кнопок под описанием продукта."""
    cms_token = context.bot_data.get('cms_full_access_token')
    cms_url = context.bot_data.get('cms_url')

    query = update.callback_query
    old_message = query.message

    query.answer()

    try:
        old_message.delete()
    except Exception as e:
        print(f'Не удалось удалить сообщение: {e}')

    if query.data == 'back_to_menu':
        send_menu(update.effective_chat.id, context)
        return 'HANDLE_MENU'
    
    elif query.data == 'add_to_cart':
        user_cart = get_cart_by_user(cms_token, cms_url, update.effective_chat.id)
        product_document_id = context.user_data.get('choosen_product_document_id')
        
        if user_cart:
            add_product_to_cart(
                cms_token,
                cms_url,
                user_cart[0]['documentId'],
                product_document_id,
            )
            send_menu(update.effective_chat.id, context)

            return 'HANDLE_MENU'
        
        else:
            user_cart = create_cart(
                cms_token,
                cms_url,
                str(update.effective_chat.id),
            )

            add_product_to_cart(
                cms_token,
                cms_url,
                user_cart['documentId'],
                product_document_id,
            )

            send_menu(update.effective_chat.id, context)

            return 'HANDLE_MENU'


def handle_users_reply(update, context):
    """
    Функция, которая запускается при любом сообщении от пользователя и решает как его обработать.
    Эта функция запускается в ответ на эти действия пользователя:
        * Нажатие на inline-кнопку в боте
        * Отправка сообщения боту
        * Отправка команды боту
    Она получает стейт пользователя из базы данных и запускает соответствующую функцию-обработчик (хэндлер).
    Функция-обработчик возвращает следующее состояние, которое записывается в базу данных.
    Если пользователь только начал пользоваться ботом, Telegram форсит его написать "/start",
    поэтому по этой фразе выставляется стартовое состояние.
    Если пользователь захочет начать общение с ботом заново, он также может воспользоваться этой командой.
    """
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
        user_state = db.get(chat_id).decode('utf-8')
    
    states_functions = {
        'START': start,
        'HANDLE_MENU': press_product_button,
        'HANDLE_DESCRIPTION': handle_description_buttons,
    }
    state_handler = states_functions[user_state]
    # Если вы вдруг не заметите, что python-telegram-bot перехватывает ошибки.
    # Оставляю этот try...except, чтобы код не падал молча.
    # Этот фрагмент можно переписать.
    try:
        next_state = state_handler(update, context)
        db.set(chat_id, next_state)
    except Exception as err:
        print(err)


def get_database_connection():
    """
    Возвращает конекшн с базой данных Redis, либо создаёт новый, если он ещё не создан.
    """
    global _database
    if _database is None:
        load_dotenv()
        database_number = os.getenv('DATABASE_NUMBER')
        database_host = os.getenv('DATABASE_HOST')
        database_port = os.getenv('DATABASE_PORT')
        _database = redis.Redis(
            host=database_host,
            port=database_port,
            db=database_number,
        )
    return _database


def main():
    load_dotenv()
    
    tg_token = os.getenv('TG_BOT_TOKEN')
    cms_read_token = os.environ['READ_ONLY_TOKEN']
    cms_full_access_token = os.environ['FULL_ACCESS_TOKEN']
    cms_host = os.getenv('HOST', 'localhost')
    cms_port = os.getenv('PORT', '1337')

    cms_url = f'http://{cms_host}:{cms_port}'

    updater = Updater(
        tg_token,
        request_kwargs={
            'proxy_url': 'http://127.0.0.1:2080',
        },
        use_context=True,
    )
    dispatcher = updater.dispatcher

    dispatcher.bot_data['cms_read_token'] = cms_read_token
    dispatcher.bot_data['cms_full_access_token'] = cms_full_access_token
    dispatcher.bot_data['cms_url'] = cms_url

    dispatcher.add_handler(CallbackQueryHandler(handle_users_reply))
    dispatcher.add_handler(MessageHandler(Filters.text, handle_users_reply))
    dispatcher.add_handler(CommandHandler('start', handle_users_reply))

    print('Бот запущен.')

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()