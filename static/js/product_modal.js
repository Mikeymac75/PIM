// Wait for the DOM to be fully loaded before trying to access elements
document.addEventListener('DOMContentLoaded', () => {

    // Modal DOM Elements
    const productDetailModal = document.getElementById('productDetailModal');
    const modalProductName = document.getElementById('modalProductName');
    const modalProductInfo = document.getElementById('modalProductInfo');
    const dailyConsumptionChartCanvas = document.getElementById('dailyConsumptionChart');
    const monthlyConsumptionChartCanvas = document.getElementById('monthlyConsumptionChart');

    // Attempt to get the close button. QuerySelector for class.
    const closeButton = document.querySelector('#productDetailModal .close-button');

    // Chart Instances
    let dailyChartInstance;
    let monthlyChartInstance;

    // Check if all essential modal elements are found
    if (!productDetailModal || !modalProductName || !modalProductInfo || !dailyConsumptionChartCanvas || !monthlyConsumptionChartCanvas || !closeButton) {
        console.error('Essential modal elements not found. Product modal functionality may be affected.');
        // You might want to disable features or return if critical elements are missing.
        // For now, we'll let it proceed, and individual functions will handle null checks if necessary.
    }

    function formatLabel(key) {
        // Converts snake_case or camelCase to Title Case
        const result = key.replace(/([A-Z])/g, " $1").replace(/_/g, " ");
        return result.charAt(0).toUpperCase() + result.slice(1);
    }

    // openProductModal function (globally accessible for now, or can be attached to window)
    window.openProductModal = async function(productId) {
        if (!productDetailModal) {
            console.error("Modal element not found, cannot open.");
            return;
        }
        try {
            const response = await fetch(`/product_modal_details/${productId}`);
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
            }
            const data = await response.json();

            // Populate Product Information
            if (modalProductName) {
                modalProductName.textContent = data.product_details.name || 'N/A';
            }

            if (modalProductInfo) {
                modalProductInfo.innerHTML = ''; // Clear existing items
                const detailsToShow = [
                    'name', 'category', 'subcategory', 'unit_of_measure',
                    'default_expiry_days', 'par_level', 'max_holding_amount', 'purchase_location'
                ];
                detailsToShow.forEach(key => {
                    const value = data.product_details[key];
                    const li = document.createElement('li');
                    li.innerHTML = `<strong>${formatLabel(key)}:</strong> ${value !== null && value !== undefined ? value : 'N/A'}`;
                    modalProductInfo.appendChild(li);
                });

                // --- Display new information ---

                // On-Hand Inventory
                const inventoryLi = document.createElement('li');
                inventoryLi.innerHTML = `<strong>Current On-Hand Inventory:</strong> ${data.product_details.current_on_hand_inventory !== null && data.product_details.current_on_hand_inventory !== undefined ? data.product_details.current_on_hand_inventory : 'N/A'} ${data.product_details.unit_of_measure || ''}`;
                modalProductInfo.appendChild(inventoryLi);

                // Nearest Expiry Date
                const expiryLi = document.createElement('li');
                expiryLi.innerHTML = `<strong>Nearest Expiry Date:</strong> ${data.product_details.nearest_expiry_date || 'N/A'}`;
                modalProductInfo.appendChild(expiryLi);

                // Recommended Purchase Today
                const shoppingLi = document.createElement('li');
                shoppingLi.innerHTML = `<strong>Recommended Purchase Today:</strong> ${data.shopping_list_amount_today !== null && data.shopping_list_amount_today !== undefined ? data.shopping_list_amount_today : 'N/A'} ${data.product_details.unit_of_measure || ''}`;
                modalProductInfo.appendChild(shoppingLi);

                // Inventory Concerns
                if (data.inventory_concerns && data.inventory_concerns.length > 0) {
                    const concernsOuterLi = document.createElement('li');
                    concernsOuterLi.innerHTML = `<strong>Inventory Concerns:</strong>`;
                    const concernsUl = document.createElement('ul');
                    data.inventory_concerns.forEach(concern => {
                        const concernLi = document.createElement('li');
                        concernLi.textContent = concern;
                        concernsUl.appendChild(concernLi);
                    });
                    concernsOuterLi.appendChild(concernsUl);
                    modalProductInfo.appendChild(concernsOuterLi);
                }

                // Recipes Containing Product
                if (data.recipes_containing_product && data.recipes_containing_product.length > 0) {
                    const recipesOuterLi = document.createElement('li');
                    recipesOuterLi.innerHTML = `<strong>Part of Recipes:</strong>`;
                    const recipesUl = document.createElement('ul');
                    data.recipes_containing_product.forEach(recipe => {
                        const recipeLi = document.createElement('li');
                        const recipeLink = document.createElement('a');
                        recipeLink.textContent = recipe.name;
                        recipeLink.href = `/recipes/name/${encodeURIComponent(recipe.name)}`;
                        // Optional: Add target="_blank" if you want recipes to open in a new tab
                        // recipeLink.target = "_blank";
                        recipeLi.appendChild(recipeLink);
                        recipesUl.appendChild(recipeLi);
                    });
                    recipesOuterLi.appendChild(recipesUl);
                    modalProductInfo.appendChild(recipesOuterLi);
                }
            }

            // Render Charts
            if (dailyConsumptionChartCanvas) {
                 renderDailyChart(data.daily_consumption || [], data.daily_inventory_history || []);
            }
            if (monthlyConsumptionChartCanvas) {
                renderMonthlyChart(data.monthly_consumption || []);
            }

            productDetailModal.style.display = 'block';
        } catch (error) {
            console.error('Error fetching product details:', error);
            if (modalProductInfo) {
                modalProductInfo.innerHTML = '<li>Error loading product details. Please try again later.</li>';
            }
            if (modalProductName) {
                modalProductName.textContent = "Error";
            }
             // Still display the modal to show the error message
            if (productDetailModal) productDetailModal.style.display = 'block';
        }
    }

    // closeProductModal function
    window.closeProductModal = function() {
        if (!productDetailModal) return;
        productDetailModal.style.display = 'none';

        if (dailyChartInstance) {
            dailyChartInstance.destroy();
            dailyChartInstance = null; // Clear instance
        }
        if (monthlyChartInstance) {
            monthlyChartInstance.destroy();
            monthlyChartInstance = null; // Clear instance
        }
    }

    // Event Listener for Close Button
    if (closeButton) {
        closeButton.addEventListener('click', closeProductModal);
    } else {
        console.warn("Close button not found for product detail modal.");
    }

    // Event Listener for Clicking Outside Modal
    window.addEventListener('click', (event) => {
        if (event.target === productDetailModal) {
            closeProductModal();
        }
    });

    // renderDailyChart function
    function renderDailyChart(dailyData, dailyInventoryHistory) {
        if (!dailyConsumptionChartCanvas) return;
        const ctx = dailyConsumptionChartCanvas.getContext('2d');

        // Use inventory history labels as the primary source for chart labels
        const chartLabels = dailyInventoryHistory.map(item => item.inventory_date);

        const consumptionDataValues = chartLabels.map(labelDate => {
            const consItem = dailyData.find(item => item.consumption_date === labelDate);
            return consItem ? consItem.total_quantity_consumed : 0;
        });

        const inventoryDataValues = dailyInventoryHistory.map(item => item.quantity_on_hand);

        if (dailyChartInstance) {
            dailyChartInstance.destroy();
        }

        const maxConsumption = Math.max(...consumptionDataValues, 0);
        const maxInventory = Math.max(...inventoryDataValues, 0);
        const suggestedMaxY = Math.max(maxConsumption, maxInventory) + 1;

        dailyChartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: chartLabels,
                datasets: [
                    {
                        label: 'Quantity Consumed',
                        data: consumptionDataValues,
                        borderColor: 'rgb(75, 192, 192)',
                        backgroundColor: 'rgba(75, 192, 192, 0.2)',
                        tension: 0.1,
                        fill: true,
                        yAxisID: 'y',
                    },
                    {
                        label: 'Current On-Hand Inventory',
                        data: inventoryDataValues,
                        borderColor: 'rgb(255, 99, 132)',
                        backgroundColor: 'rgba(255, 99, 132, 0.2)',
                        tension: 0.1,
                        fill: true,
                        yAxisID: 'y',
                    }
                ]
            },
            options: {
                scales: {
                    y: {
                        beginAtZero: true,
                        suggestedMax: suggestedMaxY
                    }
                },
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: true },
                    title: { display: false } // No separate title, using h4 above canvas
                }
            }
        });
    }

    // renderMonthlyChart function
    function renderMonthlyChart(monthlyData) {
        if (!monthlyConsumptionChartCanvas) return;
        const ctx = monthlyConsumptionChartCanvas.getContext('2d');

        const labels = monthlyData.map(item => item.consumption_month); // Corrected from item.month
        const dataValues = monthlyData.map(item => item.total_quantity_consumed);

        if (monthlyChartInstance) {
            monthlyChartInstance.destroy();
        }
        monthlyChartInstance = new Chart(ctx, {
            type: 'line', // Changed to line graph
            data: {
                labels: labels,
                datasets: [{
                    label: 'Quantity Consumed',
                    data: dataValues,
                    borderColor: 'rgb(153, 102, 255)',
                    backgroundColor: 'rgba(153, 102, 255, 0.2)',
                    tension: 0.1, // Added for line chart
                    fill: true,   // Added for line chart
                }]
            },
            options: {
                scales: { y: { beginAtZero: true, suggestedMax: Math.max(...dataValues, 0) + 1 } }, // Ensure y-axis adapts
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: true },
                    title: { display: false }
                }
            }
        });
    }
});
