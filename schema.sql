-- SQL Скрипт для ініціалізації бази даних у Supabase SQL Editor
-- Скопіюйте цей код та виконайте його у розділі SQL Editor у вашому кабінеті Supabase.

-- Таблиця користувачів
CREATE TABLE IF NOT EXISTS public.users (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    registered_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Таблиця результатів тестування
CREATE TABLE IF NOT EXISTS public.test_results (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT REFERENCES public.users(user_id) ON DELETE CASCADE,
    score INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Таблиця заявок (ліди)
CREATE TABLE IF NOT EXISTS public.leads (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT REFERENCES public.users(user_id) ON DELETE CASCADE,
    package_name TEXT NOT NULL,
    status TEXT DEFAULT 'pending' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Налаштування публічного доступу (опціонально, залежно від ваших налаштувань RLS)
-- Для простоти розробки RLS можна вимкнути для цих таблиць, або налаштувати політики доступу.
ALTER TABLE public.users DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.test_results DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.leads DISABLE ROW LEVEL SECURITY;
