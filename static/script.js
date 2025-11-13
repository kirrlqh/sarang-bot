class RestaurantMenuApp {
    constructor() {
        this.categories = [];
        this.dishes = [];
        this.currentCategoryId = null;
        this.tg = window.Telegram.WebApp;

        this.init();
    }

    async init() {
        // Инициализация Telegram Web App
        this.tg.expand();
        this.tg.enableClosingConfirmation();

        // Загрузка данных
        await this.loadCategories();
        this.setupEventListeners();
    }

    async fetchFromSupabase(endpoint) {
        try {
            const response = await fetch(SUPABASE_CONFIG.url + endpoint, {
                headers: {
                    'apikey': SUPABASE_CONFIG.anonKey,
                    'Authorization': `Bearer ${SUPABASE_CONFIG.anonKey}`
                }
            });

            if (!response.ok) throw new Error('Ошибка сети');
            return await response.json();
        } catch (error) {
            console.error('Ошибка загрузки данных:', error);
            this.showError('Ошибка загрузки данных');
            return [];
        }
    }

    async loadCategories() {
        const loadingElement = document.getElementById('loading');
        loadingElement.textContent = 'Загрузка категорий...';

        this.categories = await this.fetchFromSupabase(API_ENDPOINTS.categories);

        if (this.categories.length > 0) {
            this.renderCategories();
            await this.loadDishes(this.categories[0].id);
        } else {
            loadingElement.textContent = 'Категории не найдены';
        }
    }

    async loadDishes(categoryId) {
        this.currentCategoryId = categoryId;

        const loadingElement = document.getElementById('loading');
        const dishesGrid = document.getElementById('dishesGrid');

        loadingElement.style.display = 'block';
        dishesGrid.style.display = 'none';
        loadingElement.textContent = 'Загрузка блюд...';

        const endpoint = API_ENDPOINTS.dishes.replace('{categoryId}', categoryId);
        this.dishes = await this.fetchFromSupabase(endpoint);

        this.renderDishes();

        loadingElement.style.display = 'none';
        dishesGrid.style.display = 'grid';
    }

    renderCategories() {
        const tabsContainer = document.getElementById('categoriesTabs');

        this.categories.forEach(category => {
            const tab = document.createElement('button');
            tab.className = 'tab';
            tab.textContent = category.name;
            tab.dataset.categoryId = category.id;

            if (category.id === this.currentCategoryId) {
                tab.classList.add('active');
            }

            tab.addEventListener('click', () => {
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                this.loadDishes(category.id);
            });

            tabsContainer.appendChild(tab);
        });
    }

    renderDishes() {
        const dishesGrid = document.getElementById('dishesGrid');
        dishesGrid.innerHTML = '';

        if (this.dishes.length === 0) {
            dishesGrid.innerHTML = `
                <div style="grid-column: 1/-1; text-align: center; padding: 40px; color: #888;">
                    В этой категории пока нет блюд
                </div>
            `;
            return;
        }

        this.dishes.forEach(dish => {
            const dishCard = this.createDishCard(dish);
            dishesGrid.appendChild(dishCard);
        });
    }

    createDishCard(dish) {
        const card = document.createElement('div');
        card.className = 'dish-card';

        const features = this.getDishFeatures(dish);

        card.innerHTML = `
            ${dish.photo_file_id ?
                `<img src="${dish.photo_file_id}" alt="${dish.name}" class="dish-image" onerror="this.style.display='none'">` :
                '<div class="dish-image" style="display: flex; align-items: center; justify-content: center; color: #666;">📷</div>'
            }
            <div class="dish-name">${this.escapeHtml(dish.name)}</div>
            ${dish.composition ? `<div class="dish-composition">${this.escapeHtml(dish.composition)}</div>` : ''}
            ${features ? `<div class="dish-features">${features}</div>` : ''}
            <div class="dish-price">${dish.price ? `${dish.price} ₽` : 'Цена не указана'}</div>
            <div class="korean-pattern"></div>
        `;

        card.addEventListener('click', () => this.showDishDetails(dish));
        return card;
    }

    getDishFeatures(dish) {
        const features = [];

        if (dish.spiciness) {
            features.push(`<span class="feature-badge">🌶 ${dish.spiciness}</span>`);
        }

        if (dish.features) {
            dish.features.split(',').forEach(feature => {
                if (feature.trim()) {
                    features.push(`<span class="feature-badge">${feature.trim()}</span>`);
                }
            });
        }

        return features.join('');
    }

    showDishDetails(dish) {
        const modal = document.getElementById('dishModal');
        const modalBody = document.getElementById('modalBody');

        modalBody.innerHTML = `
            ${dish.photo_file_id ?
                `<img src="${dish.photo_file_id}" alt="${dish.name}" class="modal-image">` :
                '<div style="height: 200px; display: flex; align-items: center; justify-content: center; background: #2a2a2a; border-radius: 8px; margin-bottom: 15px; color: #666;">📷 Изображение отсутствует</div>'
            }
            <div class="modal-title">${this.escapeHtml(dish.name)}</div>

            ${dish.composition ? `
                <div class="modal-section">
                    <h4>Состав</h4>
                    <p>${this.escapeHtml(dish.composition)}</p>
                </div>
            ` : ''}

            ${dish.description ? `
                <div class="modal-section">
                    <h4>Описание</h4>
                    <p>${this.escapeHtml(dish.description)}</p>
                </div>
            ` : ''}

            ${dish.allergens ? `
                <div class="modal-section">
                    <h4>Аллергены</h4>
                    <p>${this.escapeHtml(dish.allergens)}</p>
                </div>
            ` : ''}

            ${this.getDishFeatures(dish) ? `
                <div class="modal-section">
                    <h4>Особенности</h4>
                    <div class="dish-features">${this.getDishFeatures(dish)}</div>
                </div>
            ` : ''}

            <div class="modal-price">
                ${dish.price ? `${dish.price} ₽` : 'Цена не указана'}
            </div>
        `;

        modal.style.display = 'block';
    }

    setupEventListeners() {
        // Закрытие модального окна
        document.querySelector('.close').addEventListener('click', () => {
            document.getElementById('dishModal').style.display = 'none';
        });

        // Закрытие модального окна при клике вне его
        window.addEventListener('click', (event) => {
            const modal = document.getElementById('dishModal');
            if (event.target === modal) {
                modal.style.display = 'none';
            }
        });
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    showError(message) {
        const dishesGrid = document.getElementById('dishesGrid');
        dishesGrid.innerHTML = `
            <div style="grid-column: 1/-1; text-align: center; padding: 40px; color: #ff6b6b;">
                ❌ ${message}
            </div>
        `;
    }
}

// Инициализация приложения после загрузки DOM
document.addEventListener('DOMContentLoaded', () => {
    new RestaurantMenuApp();
});