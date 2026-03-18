-- Backend/AstroAPI/migrations/001_user_connections.sql
-- Rodar no Supabase Dashboard → SQL Editor

CREATE TABLE IF NOT EXISTS public.user_connections (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  name text NOT NULL,
  birth_date date NOT NULL,
  birth_time time,
  birth_city text,
  birth_lat float,
  birth_lon float,
  created_at timestamptz DEFAULT now()
);

ALTER TABLE public.user_connections ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users_own_connections" ON public.user_connections
  FOR ALL
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

CREATE INDEX idx_user_connections_user_id ON public.user_connections(user_id);
