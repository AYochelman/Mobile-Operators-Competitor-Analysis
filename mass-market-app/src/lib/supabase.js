import { createClient } from '@supabase/supabase-js'

// Supabase anon key is public (safe to include in client code)
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'https://gmfefvjdmgzluwffzrzj.supabase.co'
const supabaseKey = import.meta.env.VITE_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdtZmVmdmpkbWd6bHV3ZmZ6cnpqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU1MTcwNzIsImV4cCI6MjA5MTA5MzA3Mn0.8RAX8o8yPHXSTYk_Fc3bmlk5fz4X5sl53k0SWNbHlvM'

export const supabase = createClient(supabaseUrl, supabaseKey)
