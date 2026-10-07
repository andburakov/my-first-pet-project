# Telegram character-count bot

The bot replies to each incoming text message with its length in Python Unicode characters and saves both the incoming message and its reply in `public.chat_logs`.

## Configure

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy its token.
2. In the Supabase dashboard, open **Project Settings → API** and copy the `service_role` (or Secret) key. This key is used only on this computer to write the log while RLS remains enabled.
3. In this directory, create `.env` from `.env.example` and add both secrets. Do not commit `.env`.

## Run

From the repository root:

```sh
python3 telegram_char_bot/bot.py
```

Open a Telegram chat with the bot and send it a text message. The terminal confirms that the bot is running; press `Ctrl+C` to stop it.

The bot records its last processed Telegram update in `bot_state.json`, so restarts do not re-log old messages.
