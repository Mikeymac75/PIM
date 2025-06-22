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
            // The daily chart will now be handled by updateProjectionDisplay
            // if (dailyConsumptionChartCanvas) {
            //      renderDailyChart(data.daily_consumption || [], data.daily_inventory_history || []);
            // }
            if (monthlyConsumptionChartCanvas) {
                renderMonthlyChart(data.monthly_consumption || []); // Keep monthly historical chart
            }

            // New: Update display with projection data (chart and depletion date)
            updateProjectionDisplay(data.future_projection_data || []);


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

    // This function will now handle the new projection data for the daily chart
    // and also display the depletion date.
    function updateProjectionDisplay(futureProjectionData) {
        const depletionDateElement = document.getElementById('productDepletionDateInfo'); // Assuming this element exists

        if (!futureProjectionData || !Array.isArray(futureProjectionData) || futureProjectionData.length === 0) {
            if (dailyChartInstance) {
                dailyChartInstance.destroy();
                dailyChartInstance = null;
            }
            if (dailyConsumptionChartCanvas) {
                 // Optional: Display a message on the canvas itself, or hide it
                const ctx = dailyConsumptionChartCanvas.getContext('2d');
                ctx.clearRect(0, 0, dailyConsumptionChartCanvas.width, dailyConsumptionChartCanvas.height);
                ctx.textAlign = 'center';
                ctx.fillText('Future projection data not available.', dailyConsumptionChartCanvas.width / 2, dailyConsumptionChartCanvas.height / 2);
            }
            if (depletionDateElement) {
                depletionDateElement.textContent = 'Future projection data not available.';
            }
            return;
        }

        // Display Depletion Date
        let depletionDateFound = false;
        if (depletionDateElement) {
            for (const item of futureProjectionData) {
                if (item.depletion_date_reached === true) {
                    const depletionDate = new Date(item.date + 'T00:00:00'); // Ensure date is parsed as local
                    depletionDateElement.textContent = `Projected to deplete on: ${depletionDate.toLocaleDateString()}`;
                    depletionDateFound = true;
                    break;
                }
            }
            if (!depletionDateFound) {
                depletionDateElement.textContent = `Inventory not expected to deplete in the next ${futureProjectionData.length} days.`;
            }
        }


        // Graph Data Preparation (7-Day Window)
        const sevenDayProjection = futureProjectionData.slice(0, 7);

        const chartLabels = sevenDayProjection.map(item => {
            const date = new Date(item.date + 'T00:00:00'); // Ensure date is parsed as local
            return `${date.getMonth() + 1}-${date.getDate()}`; // Format as MM-DD
        });

        const projectedInventoryData = sevenDayProjection.map(item => item.projected_ending_inventory);
        const consumptionData = sevenDayProjection.map(item => item.consumption);
        const shrinkData = sevenDayProjection.map(item => item.shrink);
        const harvestData = sevenDayProjection.map(item => item.harvest);

        renderFutureProjectionChart(chartLabels, projectedInventoryData, consumptionData, shrinkData, harvestData);
    }


    // Renamed and refactored from renderDailyChart
    function renderFutureProjectionChart(labels, inventoryData, consumptionData, shrinkData, harvestData) {
        if (!dailyConsumptionChartCanvas) return;
        const ctx = dailyConsumptionChartCanvas.getContext('2d');

        if (dailyChartInstance) {
            dailyChartInstance.destroy();
        }

        // Determine suggestedMax for y-axis
        const maxInventory = Math.max(...inventoryData, 0);
        const maxOthers = Math.max(...consumptionData, ...shrinkData, ...harvestData, 0);
        const suggestedMaxY = Math.max(maxInventory, maxOthers) + Math.max(maxInventory, maxOthers)*0.1; // Add 10% buffer or a fixed amount

        dailyChartInstance = new Chart(ctx, {
            type: 'line', // Base type, individual datasets can override
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Projected Inventory',
                        data: inventoryData,
                        borderColor: 'rgb(54, 162, 235)',  // Blue
                        backgroundColor: 'rgba(54, 162, 235, 0.2)',
                        tension: 0.1,
                        fill: true,
                        yAxisID: 'y',
                        type: 'line'
                    },
                    {
                        label: 'Projected Consumption',
                        data: consumptionData,
                        borderColor: 'rgb(255, 159, 64)', // Orange
                        backgroundColor: 'rgba(255, 159, 64, 0.2)',
                        tension: 0.1,
                        fill: false, // Better as a line without fill if overlapping with inventory
                        yAxisID: 'y',
                        type: 'line' // Or 'bar'
                    },
                    {
                        label: 'Projected Shrink',
                        data: shrinkData,
                        borderColor: 'rgb(255, 99, 132)',   // Red
                        backgroundColor: 'rgba(255, 99, 132, 0.2)',
                        tension: 0.1,
                        fill: false,
                        yAxisID: 'y',
                        type: 'line' // Or 'bar'
                    },
                    {
                        label: 'Projected Harvest',
                        data: harvestData,
                        borderColor: 'rgb(75, 192, 75)',    // Green
                        backgroundColor: 'rgba(75, 192, 75, 0.2)',
                        tension: 0.1,
                        fill: false,
                        yAxisID: 'y',
                        type: 'bar' // Bar might be good for discrete daily harvest amounts
                    }
                ]
            },
            options: {
                scales: {
                    y: {
                        beginAtZero: true,
                        suggestedMax: suggestedMaxY > 0 ? suggestedMaxY : 10, // Ensure a minimum height for y-axis if all data is 0
                        title: {
                            display: true,
                            text: 'Quantity'
                        }
                    },
                    x: {
                         title: {
                            display: true,
                            text: 'Date (Next 7 Days)'
                        }
                    }
                },
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: true },
                    title: { display: true, text: '7-Day Inventory Projection' }
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
