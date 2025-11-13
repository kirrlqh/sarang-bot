// Конфигурация Supabase
const SUPABASE_CONFIG = {
    url: 'https://oxvtvzrwjsqufzcokrrd.supabase.co',
    anonKey: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im94dnR2enJ3anNxdWZ6Y29rcnJkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjI3NjQ4NzEsImV4cCI6MjA3ODM0MDg3MX0.0e6BSNVui2OjtxZ6WoB0LOxQ9p6wa1R5oCKcrnuLIiI'
};

// Конфигурация API endpoints
const API_ENDPOINTS = {
    categories: '/rest/v1/categories?select=*&order=sort_order',
    dishes: '/rest/v1/dishes?select=*&category_id=eq.{categoryId}&is_available=eq.true&order=sort_order'
};