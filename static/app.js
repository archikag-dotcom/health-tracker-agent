// Health Tracker Agent - Client Application Logic

document.addEventListener('DOMContentLoaded', () => {
  const dateSelector = document.getElementById('dateSelector');
  const today = new Date().toISOString().split('T')[0];
  dateSelector.value = today;

  let currentProfile = null;
  let loggedMeals = [];

  // --- Initial Data Load ---
  fetchProfile();
  fetchMeals(today);

  // --- Date Picker Change Event ---
  dateSelector.addEventListener('change', (e) => {
    fetchMeals(e.target.value);
  });

  // --- Tab Switcher Logic ---
  const tabBtnText = document.getElementById('tabBtnText');
  const tabBtnImage = document.getElementById('tabBtnImage');
  const paneText = document.getElementById('paneText');
  const paneImage = document.getElementById('paneImage');

  tabBtnText.addEventListener('click', () => {
    tabBtnText.classList.add('active');
    tabBtnImage.classList.remove('active');
    paneText.classList.add('active');
    paneImage.classList.remove('active');
  });

  tabBtnImage.addEventListener('click', () => {
    tabBtnImage.classList.add('active');
    tabBtnText.classList.remove('active');
    paneImage.classList.add('active');
    paneText.classList.remove('active');
  });

  // --- Text Meal Logger Form Submit ---
  const textMealForm = document.getElementById('textMealForm');
  textMealForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const rawText = document.getElementById('textMealInput').value.trim();
    if (!rawText) return;

    const selectedMealType = document.querySelector('input[name="mealType"]:checked').value;
    const selectedDate = dateSelector.value;

    try {
      const resp = await fetch('/api/meals/log-text', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          raw_text: rawText,
          meal_type: selectedMealType,
          date_str: selectedDate
        })
      });
      const data = await resp.json();
      if (data.success) {
        document.getElementById('textMealInput').value = '';
        fetchMeals(selectedDate);
      } else {
        alert('Error logging meal: ' + JSON.stringify(data.error));
      }
    } catch (err) {
      alert('Network error logging meal: ' + err.message);
    }
  });

  // --- Image Dropzone & File Upload ---
  const dropzone = document.getElementById('dropzone');
  const imageFileInput = document.getElementById('imageFileInput');

  dropzone.addEventListener('click', () => imageFileInput.click());
  imageFileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      uploadMealPhoto(e.target.files[0]);
    }
  });

  async function uploadMealPhoto(file) {
    const selectedMealType = document.querySelector('input[name="imgMealType"]:checked').value;
    const selectedDate = dateSelector.value;
    const formData = new FormData();
    formData.append('file', file);
    formData.append('meal_type', selectedMealType);
    formData.append('date_str', selectedDate);

    try {
      const resp = await fetch('/api/meals/log-image', {
        method: 'POST',
        body: formData
      });
      const data = await resp.json();
      if (data.success) {
        fetchMeals(selectedDate);
      } else {
        alert('Error analyzing photo: ' + JSON.stringify(data.error));
      }
    } catch (err) {
      alert('Upload error: ' + err.message);
    }
  }

  // --- Fetch Profile & Render Targets ---
  async function fetchProfile() {
    try {
      const resp = await fetch('/api/profile');
      currentProfile = await resp.json();
      renderProfileTargets();
    } catch (err) {
      console.error('Error loading profile:', err);
    }
  }

  function renderProfileTargets() {
    if (!currentProfile) return;
    document.getElementById('targetCaloriesVal').textContent = currentProfile.daily_calories_target;
    document.getElementById('targetProteinVal').textContent = currentProfile.daily_protein_target_g;
    document.getElementById('targetCarbsVal').textContent = currentProfile.daily_carbs_target_g;
    document.getElementById('targetFatVal').textContent = currentProfile.daily_fat_target_g;
    document.getElementById('targetFiberVal').textContent = currentProfile.daily_fiber_target_g;

    // Populate profile modal inputs
    document.getElementById('profName').value = currentProfile.name;
    document.getElementById('profWeight').value = currentProfile.weight_kg;
    document.getElementById('profGoal').value = currentProfile.fitness_goal;
    document.getElementById('profCalories').value = currentProfile.daily_calories_target;
    document.getElementById('profProtein').value = currentProfile.daily_protein_target_g;
    document.getElementById('profCarbs').value = currentProfile.daily_carbs_target_g;
    document.getElementById('profFat').value = currentProfile.daily_fat_target_g;
  }

  // --- Fetch Meals for Selected Date ---
  async function fetchMeals(dateStr) {
    try {
      const resp = await fetch(`/api/meals?date=${dateStr}`);
      const data = await resp.json();
      loggedMeals = data.meals || [];
      renderDashboardOverview();
      renderMealsTimeline();
    } catch (err) {
      console.error('Error fetching meals:', err);
    }
  }

  // --- Render Dashboard Caloric Ring & Macro Progress Bars ---
  function renderDashboardOverview() {
    let totCal = 0, totProt = 0, totCarbs = 0, totFat = 0, totFiber = 0;
    loggedMeals.forEach(m => {
      totCal += m.total_macros.calories;
      totProt += m.total_macros.protein_g;
      totCarbs += m.total_macros.carbs_g;
      totFat += m.total_macros.fat_g;
      totFiber += m.total_macros.fiber_g;
    });

    const targetCal = currentProfile ? currentProfile.daily_calories_target : 2200;
    const targetProt = currentProfile ? currentProfile.daily_protein_target_g : 165;
    const targetCarbs = currentProfile ? currentProfile.daily_carbs_target_g : 220;
    const targetFat = currentProfile ? currentProfile.daily_fat_target_g : 65;
    const targetFiber = currentProfile ? currentProfile.daily_fiber_target_g : 30;

    // Update Calorie Display
    document.getElementById('consumedCaloriesVal').textContent = Math.round(totCal);
    const remainingCal = Math.max(0, Math.round(targetCal - totCal));
    document.getElementById('remainingCaloriesVal').textContent = remainingCal;

    // Update Calorie SVG Ring (stroke-dasharray = 534)
    const calPct = Math.min(1.0, totCal / targetCal);
    const ringDashoffset = 534 - (534 * calPct);
    document.getElementById('calorieRingProgress').style.strokeDashoffset = ringDashoffset;

    // Update Macro Values & Bar Fills
    document.getElementById('consumedProteinVal').textContent = totProt.toFixed(1);
    document.getElementById('fillProtein').style.width = Math.min(100, (totProt / targetProt) * 100) + '%';

    document.getElementById('consumedCarbsVal').textContent = totCarbs.toFixed(1);
    document.getElementById('fillCarbs').style.width = Math.min(100, (totCarbs / targetCarbs) * 100) + '%';

    document.getElementById('consumedFatVal').textContent = totFat.toFixed(1);
    document.getElementById('fillFat').style.width = Math.min(100, (totFat / targetFat) * 100) + '%';

    document.getElementById('consumedFiberVal').textContent = totFiber.toFixed(1);
    document.getElementById('fillFiber').style.width = Math.min(100, (totFiber / targetFiber) * 100) + '%';
  }

  // --- Render Logged Meals Timeline Feed ---
  function renderMealsTimeline() {
    const container = document.getElementById('mealsContainer');
    if (loggedMeals.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; padding: 40px; color: var(--text-muted); background: var(--bg-card); border-radius: var(--radius-lg); border: 1px dashed var(--border-glass);">
          <div style="font-size: 2.2rem; margin-bottom: 8px;">🥣</div>
          <div>No meals logged yet for this date. Use text or photo logger above to add a meal!</div>
        </div>`;
      return;
    }

    const mealIcons = { breakfast: '🌅', lunch: '☀️', dinner: '🌙', snack: '🍏' };

    container.innerHTML = loggedMeals.map(meal => {
      const icon = mealIcons[meal.meal_type] || '🍽️';
      const itemChips = meal.items.map(it => `<span class="item-chip">${it.quantity} ${it.unit} ${it.name} (${it.macros.calories} kcal)</span>`).join('');
      
      return `
        <div class="meal-card">
          <div class="meal-main-info">
            <div class="meal-badge">${icon}</div>
            <div class="meal-details-text">
              <h4>${meal.meal_type.toUpperCase()} <span style="font-size: 0.85rem; font-weight: 500; color: var(--text-muted);">(${meal.total_macros.calories} kcal)</span></h4>
              <div class="meal-raw-input">${meal.input_type === 'image' ? '📸 Photo Analysis: ' : '✍️ '}${meal.raw_input}</div>
              <div class="meal-item-chips">${itemChips}</div>
            </div>
          </div>
          <div class="meal-macro-summary">
            <div class="macro-chip-group">
              <div class="m-chip"><span class="m-chip-val" style="color: var(--primary-emerald);">${meal.total_macros.protein_g}g</span><span class="m-chip-lbl">Protein</span></div>
              <div class="m-chip"><span class="m-chip-val" style="color: var(--primary-cyan);">${meal.total_macros.carbs_g}g</span><span class="m-chip-lbl">Carbs</span></div>
              <div class="m-chip"><span class="m-chip-val" style="color: var(--accent-amber);">${meal.total_macros.fat_g}g</span><span class="m-chip-lbl">Fat</span></div>
            </div>
            <button class="btn-delete" onclick="deleteMealItem('${meal.id}')" title="Delete meal">&times;</button>
          </div>
        </div>`;
    }).join('');
  }

  // --- Delete Meal Item ---
  window.deleteMealItem = async function(mealId) {
    const selectedDate = dateSelector.value;
    try {
      const resp = await fetch(`/api/meals/${mealId}?date=${selectedDate}`, { method: 'DELETE' });
      const data = await resp.json();
      if (data.success) {
        fetchMeals(selectedDate);
      }
    } catch (err) {
      alert('Error deleting meal: ' + err.message);
    }
  };

  // --- Quick Prompt & Sample Image Helper Functions ---
  window.fillPrompt = function(str) {
    document.getElementById('textMealInput').value = str;
  };

  window.logSampleImage = async function(imagePath, contextName) {
    const selectedDate = dateSelector.value;
    const selectedMealType = document.querySelector('input[name="imgMealType"]:checked').value;

    const formData = new FormData();
    formData.append('file', new File(["dummy"], imagePath, { type: "image/png" }));
    formData.append('meal_type', selectedMealType);
    formData.append('date_str', selectedDate);
    formData.append('additional_context', contextName);

    try {
      const resp = await fetch('/api/meals/log-image', {
        method: 'POST',
        body: formData
      });
      const data = await resp.json();
      if (data.success) {
        fetchMeals(selectedDate);
      }
    } catch (err) {
      alert('Error logging sample image: ' + err.message);
    }
  };

  // --- Daily Report Modal Handler ---
  const btnGenerateReport = document.getElementById('btnGenerateReport');
  const reportModal = document.getElementById('reportModal');
  const btnCloseReport = document.getElementById('btnCloseReport');

  btnGenerateReport.addEventListener('click', async () => {
    const selectedDate = dateSelector.value;
    document.getElementById('reportDateHeader').textContent = `Evaluating Subagent Macro Calculations for ${selectedDate}`;
    
    try {
      const resp = await fetch(`/api/reports/daily?date=${selectedDate}`);
      const data = await resp.json();
      if (data.success && data.report) {
        const markdown = data.report.report_markdown;
        document.getElementById('reportMarkdownContainer').innerHTML = marked.parse(markdown);
        reportModal.classList.add('active');
      } else {
        alert('Error generating report: ' + JSON.stringify(data.error));
      }
    } catch (err) {
      alert('Error fetching daily report: ' + err.message);
    }
  });

  btnCloseReport.addEventListener('click', () => reportModal.classList.remove('active'));

  // --- Profile Modal Handler ---
  const btnOpenProfile = document.getElementById('btnOpenProfile');
  const profileModal = document.getElementById('profileModal');
  const btnCloseProfile = document.getElementById('btnCloseProfile');
  const profileForm = document.getElementById('profileForm');

  btnOpenProfile.addEventListener('click', () => profileModal.classList.add('active'));
  btnCloseProfile.addEventListener('click', () => profileModal.classList.remove('active'));

  profileForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const payload = {
      name: document.getElementById('profName').value,
      weight_kg: parseFloat(document.getElementById('profWeight').value),
      fitness_goal: document.getElementById('profGoal').value,
      daily_calories_target: parseFloat(document.getElementById('profCalories').value),
      daily_protein_target_g: parseFloat(document.getElementById('profProtein').value),
      daily_carbs_target_g: parseFloat(document.getElementById('profCarbs').value),
      daily_fat_target_g: parseFloat(document.getElementById('profFat').value),
    };

    try {
      const resp = await fetch('/api/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await resp.json();
      if (data.success) {
        currentProfile = data.profile;
        renderProfileTargets();
        renderDashboardOverview();
        profileModal.classList.remove('active');
      }
    } catch (err) {
      alert('Error saving profile: ' + err.message);
    }
  });

});
