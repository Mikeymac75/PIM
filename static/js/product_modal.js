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
            // Pass both past actuals and future projections
            updateProjectionDisplay(data.past_actual_data || [], data.future_projection_data || []);


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

    // This function now handles both past actuals and future projection data for the daily chart
    // and also displays the depletion date based on future data.
    function updateProjectionDisplay(pastActualData, futureProjectionData) {
        const depletionDateElement = document.getElementById('productDepletionDateInfo'); // Assuming this element exists
        const chartCanvas = dailyConsumptionChartCanvas; // Use the existing canvas

        // --- Depletion Date (uses only futureProjectionData) ---
        if (depletionDateElement) {
            if (!futureProjectionData || !Array.isArray(futureProjectionData) || futureProjectionData.length === 0) {
                depletionDateElement.textContent = 'Future projection data for depletion not available.';
            } else {
                let depletionDateFound = false;
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
        }

        // --- Chart Data Preparation (7 days past + 7 days future) ---
        // Validate data for the chart
        const pastDataValid = Array.isArray(pastActualData) && pastActualData.length > 0; // Should be 7 ideally
        const futureDataValid = Array.isArray(futureProjectionData) && futureProjectionData.length > 0;

        if (!pastDataValid || !futureDataValid) {
            if (dailyChartInstance) {
                dailyChartInstance.destroy();
                dailyChartInstance = null;
            }
            if (chartCanvas) {
                const ctx = chartCanvas.getContext('2d');
                ctx.clearRect(0, 0, chartCanvas.width, chartCanvas.height);
                ctx.textAlign = 'center';
                ctx.fillText('Past or Future data not sufficient for combined chart.', chartCanvas.width / 2, chartCanvas.height / 2);
            }
            return;
        }

        const sevenDayFuture = futureProjectionData.slice(0, 7);
        // Assuming pastActualData is already the last 7 days from the backend
        const combinedData = pastActualData.concat(sevenDayFuture);

        const chartLabels = combinedData.map(item => {
            const dateObj = new Date(item.date + 'T00:00:00'); // Ensure date is parsed as local
            return `${dateObj.getMonth() + 1}-${dateObj.getDate()}`; // Format as MM-DD
        });

        const inventoryLineData = combinedData.map((item, index) =>
            index < pastActualData.length ? item.actual_ending_inventory : item.projected_ending_inventory
        );
        const consumptionLineData = combinedData.map((item, index) =>
            index < pastActualData.length ? item.actual_consumption : item.consumption
        );
        const shrinkLineData = combinedData.map((item, index) =>
            index < pastActualData.length ? item.actual_shrink : item.shrink // actual_shrink is currently 0
        );
        const harvestBarData = combinedData.map((item, index) =>
            index < pastActualData.length ? item.actual_harvest : item.harvest // actual_harvest is currently 0
        );

        renderCombinedChart(chartLabels, inventoryLineData, consumptionLineData, shrinkLineData, harvestBarData);
    }

    // Renamed and refactored to render the combined 14-day view
    function renderCombinedChart(labels, inventoryData, consumptionData, shrinkData, harvestData) {
        if (!dailyConsumptionChartCanvas) return;
        const ctx = dailyConsumptionChartCanvas.getContext('2d');

        if (dailyChartInstance) {
            dailyChartInstance.destroy();
        }

        const maxInventory = Math.max(...inventoryData, 0);
        const maxOthers = Math.max(...consumptionData, ...shrinkData, ...harvestData, 0);
        const suggestedMaxY = Math.max(maxInventory, maxOthers) * 1.1 || 10; // 10% buffer or 10 if all zero


        // Optional: Add a plugin for a vertical line at "today"
        const todayLinePlugin = {
            id: 'todayLine',
            afterDraw: (chart) => {
                if (chart.data.labels.length > 7) { // Only draw if there's enough data for past/future
                    const ctxPlugin = chart.ctx;
                    const xAxis = chart.scales.x;
                    const yAxis = chart.scales.y;
                    // Position the line between the 7th and 8th label (index 6.5)
                    const xPos = xAxis.getPixelForValue(6.5);

                    ctxPlugin.save();
                    ctxPlugin.beginPath();
                    ctxPlugin.moveTo(xPos, yAxis.top);
                    ctxPlugin.lineTo(xPos, yAxis.bottom);
                    ctxPlugin.lineWidth = 1;
                    ctxPlugin.strokeStyle = 'rgba(128, 128, 128, 0.5)'; // Grey color for the line
                    ctxPlugin.stroke();

                    // Add "Today" text
                    ctxPlugin.textAlign = 'center';
                    ctxPlugin.fillStyle = 'rgba(128, 128, 128, 0.8)';
                    ctxPlugin.fillText("Today", xPos, yAxis.top + 10); // Adjust y for text position
                    ctxPlugin.restore();
                }
            }
        };


        dailyChartInstance = new Chart(ctx, {
            type: 'line',
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
                        suggestedMax: suggestedMaxY,
                        title: {
                            display: true,
                            text: 'Quantity'
                        }
                    },
                    x: {
                         title: {
                            display: true,
                            text: 'Date (7 Days Past / 7 Days Future)'
                        }
                    }
                },
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: true },
                    title: { display: true, text: 'Inventory Actuals & Projection (Past 7 / Future 7 Days)' },
                    todayLine: todayLinePlugin // Register the custom plugin if used
                }
            },
            plugins: [todayLinePlugin] // Register plugin instance
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

    // --- Add to Shopping List Button Handlers ---

    // Generic handler for ".add-to-sl-button" clicks (outside the modal)
    document.body.addEventListener('click', function(event) {
        if (event.target.matches('.add-to-sl-button')) {
            event.preventDefault();
            const button = event.target;
            const productId = button.dataset.productId;
            const productName = button.dataset.productName || `Product ID ${productId}`;

            const quantityStr = prompt(`Enter quantity of '${productName}' to add to your shopping list:`, "1");
            if (quantityStr === null) return; // User cancelled

            const quantity = parseFloat(quantityStr);
            if (isNaN(quantity) || quantity <= 0) {
                alert("Invalid quantity. Please enter a positive number.");
                return;
            }

            // Create a hidden form and submit
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = '/shopping_list/add_direct'; // URL for direct add

            const productIdInput = document.createElement('input');
            productIdInput.type = 'hidden';
            productIdInput.name = 'product_id';
            productIdInput.value = productId;
            form.appendChild(productIdInput);

            const quantityInput = document.createElement('input');
            quantityInput.type = 'hidden';
            quantityInput.name = 'quantity';
            quantityInput.value = quantity;
            form.appendChild(quantityInput);

            // Add CSRF token if your app uses Flask-WTF or similar for CSRF protection on POSTs
            // const csrfTokenInput = document.createElement('input');
            // csrfTokenInput.type = 'hidden';
            // csrfTokenInput.name = 'csrf_token';
            // csrfTokenInput.value = '{{ csrf_token() }}'; // This template tag won't work in JS. Get from a meta tag or data attribute.
            // For now, assuming no CSRF token needed for this specific AJAX endpoint or it's handled differently.

            document.body.appendChild(form);
            form.submit();
            // No need to remove form as page will reload or redirect.
            // If it were an AJAX submit here, you would handle response and remove form.
        }
    });

    // Handler for the "Add to SL" button WITHIN the product modal
    const modalAddToSLButton = document.getElementById('modalAddToSLButton');
    const modalProductQuantityInput = document.getElementById('modalProductQuantity');

    if (modalAddToSLButton && modalProductQuantityInput) {
        modalAddToSLButton.addEventListener('click', async function() {
            const productId = this.dataset.productId; // Assume product ID is set on this button when modal opens
            const productName = this.dataset.productName || `Product ID ${productId}`;
            const quantityStr = modalProductQuantityInput.value;

            if (!productId) {
                alert("Error: Product ID not found for modal 'Add to SL' button.");
                return;
            }

            const quantity = parseFloat(quantityStr);
            if (isNaN(quantity) || quantity <= 0) {
                alert(`Invalid quantity for '${productName}'. Please enter a positive number.`);
                modalProductQuantityInput.focus();
                return;
            }

            try {
                const formData = new FormData();
                formData.append('product_id', productId);
                formData.append('quantity', quantity);
                // Add CSRF token if needed, similar to above.

                const response = await fetch('/shopping_list/add_direct', {
                    method: 'POST',
                    body: formData
                    // If sending JSON:
                    // headers: { 'Content-Type': 'application/json' },
                    // body: JSON.stringify({ product_id: productId, quantity: quantity })
                });

                const result = await response.json();

                if (response.ok && result.success) {
                    alert(result.message || `Successfully added ${quantity} of '${productName}' to shopping list!`);
                    // Optionally close modal or update UI
                    // closeProductModal();
                } else {
                    alert(result.message || `Failed to add '${productName}' to shopping list.`);
                }
            } catch (error) {
                console.error("Error adding item to shopping list via modal:", error);
                alert(`An error occurred: ${error.message || "Could not connect to server."}`);
            }
        });
    } else {
        if (!modalAddToSLButton) console.warn("Modal 'Add to SL' button (modalAddToSLButton) not found.");
        if (!modalProductQuantityInput) console.warn("Modal quantity input (modalProductQuantity) not found.");
    }
     // Ensure openProductModal sets the product ID on the modal's "Add to SL" button
     // This is a modification of the existing openProductModal function
    const originalOpenProductModal = window.openProductModal;
    window.openProductModal = async function(productId) {
        // Call the original function first
        if (originalOpenProductModal) {
            await originalOpenProductModal(productId); // Wait for it to complete
        } else {
            // Fallback or error if original is somehow not defined (should not happen if script order is correct)
            console.error("Original openProductModal function not found. Cannot enhance.");
            // Attempt to show basic modal content if original is missing
            if (productDetailModal) productDetailModal.style.display = 'block';
            if (modalProductName) modalProductName.textContent = `Product ID ${productId}`;
            if (modalProductInfo) modalProductInfo.innerHTML = '<li>Details unavailable due to script error.</li>';
        }


        // Now, specifically set the product ID for the modal's "Add to SL" button
        if (modalAddToSLButton) {
            modalAddToSLButton.dataset.productId = productId;
            // Fetch product name again if needed for the button's dataset, or rely on modalProductName
            const productNameForButton = document.getElementById('modalProductName')?.textContent || `Product ID ${productId}`;
            modalAddToSLButton.dataset.productName = productNameForButton;
        }
        if (modalProductQuantityInput) {
            modalProductQuantityInput.value = "1"; // Default quantity to 1
        }
    };

});
