export interface MappedCategoryResult {
  categoryId?: number;
  categoryName?: string;
  defaultShelfLifeDays?: number;
}

export interface SeededCategoryRule {
  id: number;
  name: string;
  defaultShelfLifeDays: number;
  keywords: string[];
}

export const SEEDED_CATEGORIES: SeededCategoryRule[] = [
  {
    id: 1,
    name: 'Dairy',
    defaultShelfLifeDays: 10,
    keywords: [
      'dairy',
      'dairies',
      'milk',
      'milks',
      'cheese',
      'cheeses',
      'yogurt',
      'yoghurt',
      'butter',
      'paneer',
      'curd',
      'cream',
      'ghee',
      'fromage',
      'lait',
    ],
  },
  {
    id: 11,
    name: 'Fruits',
    defaultShelfLifeDays: 5,
    keywords: [
      'fruit',
      'fruits',
      'apple',
      'apples',
      'banana',
      'bananas',
      'orange',
      'oranges',
      'berry',
      'berries',
      'strawberry',
      'strawberries',
      'mango',
      'mangoes',
      'grape',
      'grapes',
      'citrus',
      'lemon',
      'lime',
    ],
  },
  {
    id: 12,
    name: 'Vegetables',
    defaultShelfLifeDays: 5,
    keywords: [
      'vegetable',
      'vegetables',
      'tomato',
      'tomatoes',
      'potato',
      'potatoes',
      'onion',
      'onions',
      'carrot',
      'carrots',
      'spinach',
      'greens',
      'lettuce',
      'cabbage',
      'broccoli',
      'cauliflower',
      'cucumber',
      'pepper',
      'peppers',
      'garlic',
    ],
  },
  {
    id: 2,
    name: 'Produce',
    defaultShelfLifeDays: 5,
    keywords: [
      'produce',
      'fresh greens',
      'salad',
      'herbs',
      'fresh',
    ],
  },
  {
    id: 3,
    name: 'Bakery',
    defaultShelfLifeDays: 4,
    keywords: [
      'bakery',
      'bread',
      'breads',
      'cake',
      'cakes',
      'pastry',
      'pastries',
      'cookie',
      'cookies',
      'biscuit',
      'biscuits',
      'toast',
      'bun',
      'buns',
      'croissant',
      'muffin',
    ],
  },
  {
    id: 4,
    name: 'Meat & Poultry',
    defaultShelfLifeDays: 3,
    keywords: [
      'meat',
      'meats',
      'poultry',
      'chicken',
      'beef',
      'pork',
      'mutton',
      'lamb',
      'fish',
      'seafood',
      'sausage',
      'ham',
      'turkey',
    ],
  },
  {
    id: 10,
    name: 'Prepared Food',
    defaultShelfLifeDays: 2,
    keywords: [
      'prepared',
      'ready-to-eat',
      'meal box',
      'thali',
      'combo meal',
    ],
  },
  {
    id: 5,
    name: 'Prepared & Cooked Meals',
    defaultShelfLifeDays: 2,
    keywords: [
      'prepared',
      'meal',
      'meals',
      'cooked',
      'sandwich',
      'sandwiches',
      'ready-to-eat',
      'deli',
      'pizza',
      'sushi',
    ],
  },
  {
    id: 6,
    name: 'Frozen Foods',
    defaultShelfLifeDays: 90,
    keywords: ['frozen', 'ice cream', 'ice-cream', 'sorbet', 'gelato', 'freezer'],
  },
  {
    id: 7,
    name: 'Dry Goods & Grains',
    defaultShelfLifeDays: 180,
    keywords: [
      'grain',
      'grains',
      'dry',
      'cereal',
      'cereals',
      'flour',
      'rice',
      'pasta',
      'noodles',
      'pulses',
      'lentils',
      'snack',
      'snacks',
      'chips',
      'cracker',
      'crackers',
      'spice',
      'spices',
      'sugar',
      'salt',
      'oil',
      'nuts',
      'seeds',
    ],
  },
  {
    id: 8,
    name: 'Canned Goods',
    defaultShelfLifeDays: 365,
    keywords: ['canned', 'tin', 'tinned', 'preserve', 'preserves', 'conserves'],
  },
  {
    id: 9,
    name: 'Beverages',
    defaultShelfLifeDays: 60,
    keywords: [
      'beverage',
      'beverages',
      'drink',
      'drinks',
      'juice',
      'juices',
      'soda',
      'tea',
      'coffee',
      'water',
      'syrup',
      'boisson',
    ],
  },
];

/**
 * Maps Open Food Facts categories text to seeded categories with a sensible default shelf life.
 * Leaves defaultShelfLifeDays undefined when category is unknown so the user must enter an expiry date.
 */
export function mapOpenFoodFactsCategory(
  rawCategoryText?: string | null,
  availableCategories?: Array<{ id: number; name: string; default_shelf_life_days?: number | null }>
): MappedCategoryResult {
  if (!rawCategoryText || !rawCategoryText.trim()) {
    return {};
  }

  const normalized = rawCategoryText.toLowerCase();

  for (const item of SEEDED_CATEGORIES) {
    for (const kw of item.keywords) {
      if (normalized.includes(kw)) {
        const matchedCategory = availableCategories?.find(
          (c) => c.name.toLowerCase() === item.name.toLowerCase() || c.id === item.id
        );
        return {
          categoryId: matchedCategory?.id || item.id,
          categoryName: matchedCategory?.name || item.name,
          defaultShelfLifeDays: matchedCategory?.default_shelf_life_days ?? item.defaultShelfLifeDays,
        };
      }
    }
  }

  // When unknown, return empty object so category and shelf life are not blindly assumed
  return {};
}
