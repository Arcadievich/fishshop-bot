import secrets
import sys
from pathlib import Path


SECRET_VARS = [
    'APP_KEYS',
    'API_TOKEN_SALT',
    'ADMIN_JWT_SECRET',
    'TRANSFER_TOKEN_SALT',
    'JWT_SECRET',
    'ENCRYPTION_KEY',
]

DATABASE_VARS = {
    'DATABASE_CLIENT': 'sqlite',
    'DATABASE_HOST': 'localhost',
    'DATABASE_PORT': '6379',
    'DATABASE_NUMBER': '0',
    'DATABASE_SSL': 'false',
    'DATABASE_FILENAME': '.tmp/data.db',
}


def generate_secret() -> str:
    """Возвращает криптостойкую случайную строку (base64-подобную)."""
    return secrets.token_urlsafe(32)


def build_secrets() -> dict:
    secrets_map = {}
    for var in SECRET_VARS:
        secrets_map[var] = generate_secret()

    secrets_map['APP_KEYS'] = f'{generate_secret()},{generate_secret()}'

    return secrets_map


def main():
    example_path = Path('.env.example')
    env_path = Path('.env')

    if not example_path.exists():
        print(f'Ошибка: файл {example_path} не найден в текущей папке.')
        sys.exit(1)

    if env_path.exists():
        answer = input('.env уже существует. Перезаписать? [y/N]: ').strip().lower()
        if answer != 'y':
            print('Отменено.')
            return

    secrets_map = build_secrets()

    lines = example_path.read_text(encoding='utf-8').splitlines()
    result_lines = []
    found_db_vars = set()

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            result_lines.append(line)
            continue

        if '=' in line:
            key, _, _ = line.partition('=')
            key = key.strip()

            if key in secrets_map:
                result_lines.append(f'{key}={secrets_map[key]}')
                continue

            if key in DATABASE_VARS:
                found_db_vars.add(key)
                result_lines.append(f'{key}={DATABASE_VARS[key]}')
                continue

        result_lines.append(line)

    # Если каких-то переменных базы данных не было в .env.example — дописываем их
    missing_db_vars = set(DATABASE_VARS) - found_db_vars
    if missing_db_vars:
        result_lines.append('\n# === Database ===')
        for var in DATABASE_VARS:
            if var in missing_db_vars:
                result_lines.append(f'{var}={DATABASE_VARS[var]}')

    env_path.write_text('\n'.join(result_lines) + '\n', encoding='utf-8')
    print(f'Готово: создан {env_path} с новыми ключами Strapi.')
    print('Параметры базы данных добавлены.')
    print('Не забудьте вписать свои TG_BOT_TOKEN и FULL_ACCESS_TOKEN.')


if __name__ == '__main__':
    main()