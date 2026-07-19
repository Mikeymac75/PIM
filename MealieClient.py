"""
MealieClient - API client for Mealie recipe manager integration.
Enables bidirectional recipe sync between PIM and Mealie.
"""

import requests
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class MealieClient:
    """Client for interacting with Mealie's REST API."""
    
    def __init__(self, base_url: str, api_token: str):
        self.base_url = base_url.rstrip('/')
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        self.timeout = 30
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict]:
        """Make an API request to Mealie."""
        url = f"{self.base_url}/api{endpoint}"
        try:
            response = requests.request(
                method, url, headers=self.headers, timeout=self.timeout, **kwargs
            )
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.RequestException as e:
            logger.error(f"Mealie API error: {e}")
            return None
    
    def test_connection(self) -> Dict[str, Any]:
        """Test the connection to Mealie."""
        result = self._request("GET", "/app/about")
        if result:
            return {"success": True, "version": result.get("version", "unknown")}
        return {"success": False, "error": "Could not connect to Mealie"}
    
    def get_all_recipes(self, page: int = 1, per_page: int = 50) -> Optional[Dict]:
        """Get all recipes with pagination."""
        return self._request("GET", f"/recipes?page={page}&perPage={per_page}")
    
    def get_recipe(self, slug: str) -> Optional[Dict]:
        """Get a single recipe by its slug."""
        return self._request("GET", f"/recipes/{slug}")
    
    def create_recipe(self, recipe_data: Dict) -> Optional[Dict]:
        """Create a new recipe in Mealie."""
        create_response = self._request("POST", "/recipes", json={"name": recipe_data.get("name", "New Recipe")})
        if not create_response:
            return None
        slug = create_response
        if isinstance(slug, str):
            return self.update_recipe(slug, recipe_data)
        return create_response
    
    def update_recipe(self, slug: str, recipe_data: Dict) -> Optional[Dict]:
        """Update an existing recipe."""
        return self._request("PATCH", f"/recipes/{slug}", json=recipe_data)
    
    def mealie_to_pim(self, mealie_recipe: Dict) -> Dict:
        """Convert a Mealie recipe to PIM format."""
        ingredients = []
        for ing in mealie_recipe.get("recipeIngredient", []):
            item_name = ing.get("food", {}).get("name") if isinstance(ing.get("food"), dict) else ing.get("note", "Unknown")
            quantity = ing.get("quantity", 1)
            unit = ing.get("unit", {}).get("name", "") if isinstance(ing.get("unit"), dict) else ""
            ingredients.append({
                "item_name": item_name or ing.get("note", "Unknown"),
                "quantity": f"{quantity} {unit}".strip() if quantity else ing.get("note", "1")
            })
        
        instructions_list = mealie_recipe.get("recipeInstructions", [])
        if isinstance(instructions_list, list):
            instructions = "\n\n".join([
                f"{i+1}. {step.get('text', '')}" 
                for i, step in enumerate(instructions_list) if isinstance(step, dict)
            ])
        else:
            instructions = str(instructions_list)
        
        return {
            "name": mealie_recipe.get("name", "Unnamed Recipe"),
            "description": mealie_recipe.get("description", ""),
            "instructions": instructions,
            "ingredients": ingredients,
            "output_yield": mealie_recipe.get("recipeYield", ""),
            "mealie_slug": mealie_recipe.get("slug", ""),
            "mealie_id": mealie_recipe.get("id", "")
        }
    
    def pim_to_mealie(self, pim_recipe: Dict) -> Dict:
        """Convert a PIM recipe to Mealie format."""
        import re
        recipe_ingredient = []
        for ing in pim_recipe.get("ingredients", []):
            recipe_ingredient.append({
                "note": f"{ing.get('quantity', '')} {ing.get('item_name', '')}".strip(),
                "quantity": None, "unit": None, "food": None
            })
        
        instructions_text = pim_recipe.get("instructions", "")
        recipe_instructions = []
        if instructions_text:
            steps = re.split(r'\d+[\.\)]\s*', instructions_text)
            steps = [s.strip() for s in steps if s.strip()]
            if not steps:
                steps = instructions_text.split('\n')
            for step in steps:
                if step.strip():
                    recipe_instructions.append({"text": step.strip()})
        
        return {
            "name": pim_recipe.get("name", "Unnamed Recipe"),
            "description": pim_recipe.get("description", ""),
            "recipeYield": pim_recipe.get("output_yield", ""),
            "recipeIngredient": recipe_ingredient,
            "recipeInstructions": recipe_instructions
        }
