document.addEventListener('DOMContentLoaded', function() {
    const taskListUL = document.getElementById('task-list');
    const newTaskTitleInput = document.getElementById('new-task-title');
    const addTaskBtn = document.getElementById('add-task-btn');

    const taskDetailContentDiv = document.getElementById('task-detail-content');
    const taskDetailFormDiv = document.getElementById('task-detail-form');
    const detailTaskIdInput = document.getElementById('detail-task-id');
    const detailTitleInput = document.getElementById('detail-title');
    const detailDueInput = document.getElementById('detail-due');
    const detailSummaryTextarea = document.getElementById('detail-summary');
    const detailUiSelect = document.getElementById('detail-ui');
    const saveTaskBtn = document.getElementById('save-task-btn');
    const completeTaskBtn = document.getElementById('complete-task-btn');

    const mslLogEntriesDiv = document.getElementById('msl-log-entries');
    const addMslEntryFormDiv = document.getElementById('add-msl-entry-form');
    const newMslTextInput = document.getElementById('new-msl-text');
    const addMslBtn = document.getElementById('add-msl-btn');

    const viewActiveTasksBtn = document.getElementById('view-active-tasks-btn');
    const viewCompletedTasksBtn = document.getElementById('view-completed-tasks-btn');
    const taskListTitle = document.getElementById('task-list-title');

    let currentTaskView = 'active'; // 'active' or 'completed'
    let currentFilter = 'Filter_UI';
    let selectedTaskId = null;

    // Define the base path for your MSL API
    const MSL_API_BASE_PATH = '/msl/api'; // Corrected base path

    async function fetchAPI(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
            }
        };
        const response = await fetch(url, { ...defaultOptions, ...options });
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ message: response.statusText }));
            console.error('API Error:', response.status, errorData);
            alert(`Error: ${errorData.error || errorData.message || 'Request failed'}`);
            throw new Error(`API request failed: ${response.status}`);
        }
        if (response.headers.get("content-type")?.includes("application/json")) {
            return response.json();
        }
        return response.text();
    }

    async function loadTasks() {
        try {
            let endpoint = `${MSL_API_BASE_PATH}/tasks?filter_by=${currentFilter}`; // Use base path
            if (currentTaskView === 'completed') {
                endpoint = `${MSL_API_BASE_PATH}/tasks/completed?filter_by=${currentFilter}`; // Use base path
                taskListTitle.textContent = 'Completed Tasks';
            } else {
                taskListTitle.textContent = 'Active Tasks';
            }

            const tasks = await fetchAPI(endpoint);
            taskListUL.innerHTML = '';
            if (tasks.length === 0) {
                const li = document.createElement('li');
                li.textContent = currentTaskView === 'active' ? 'No active tasks found.' : 'No completed tasks found.';
                taskListUL.appendChild(li);
            } else {
                tasks.forEach(task => {
                    const li = document.createElement('li');
                    li.textContent = task.Title;
                    if (task.State === 0) {
                        li.textContent += " (Completed)";
                        li.style.textDecoration = "line-through";
                        li.style.color = "#777";
                    }
                    li.dataset.taskId = task.ID;
                    li.dataset.taskState = task.State;

                    const groupKey = task[`${currentFilter}_Text`];
                    let groupHeader = taskListUL.querySelector(`[data-group="${groupKey}"]`);
                    if (!groupHeader) {
                        const headerLi = document.createElement('li');
                        headerLi.classList.add('group-header');
                        headerLi.textContent = groupKey;
                        headerLi.dataset.group = groupKey;
                        taskListUL.appendChild(headerLi);
                    }

                    li.addEventListener('click', () => {
                        loadTaskDetails(task.ID, task.State);
                        document.querySelectorAll('#task-list li').forEach(item => item.classList.remove('selected'));
                        li.classList.add('selected');
                    });
                    taskListUL.appendChild(li);
                });
            }
            if (!tasks.some(task => task.ID === selectedTaskId)) {
                clearTaskDetails();
            }
        } catch (error) {
            console.error('Failed to load tasks:', error);
            taskListUL.innerHTML = '<li>Error loading tasks.</li>';
        }
    }

    async function loadTaskDetails(taskId, taskState) {
        selectedTaskId = taskId;
        try {
            let currentListEndpoint = (currentTaskView === 'active') ? `${MSL_API_BASE_PATH}/tasks` : `${MSL_API_BASE_PATH}/tasks/completed`;
            currentListEndpoint += `?filter_by=${currentFilter}`;

            const task = await fetchAPI(currentListEndpoint)
                .then(tasks => tasks.find(t => t.ID === taskId));

            if (!task) {
                clearTaskDetails();
                taskDetailContentDiv.innerHTML = '<p>Task not found or no longer in this view.</p>';
                return;
            }

            taskDetailContentDiv.innerHTML = '';
            taskDetailFormDiv.style.display = 'block';

            detailTaskIdInput.value = task.ID;
            detailTitleInput.value = task.Title || '';
            detailSummaryTextarea.value = task.Summary || '';
            detailUiSelect.value = task.UI || '0';
            if (task.Due) {
                detailDueInput.value = task.Due.startsWith('0000-00-00') || task.Due.startsWith('9999-12-31') ? '' : task.Due.substring(0, 10);
            } else {
                detailDueInput.value = '';
            }

            if (taskState === 0) { // Completed task
                completeTaskBtn.style.display = 'none';
                addMslEntryFormDiv.style.display = 'block';
                detailTitleInput.readOnly = true;
                detailDueInput.readOnly = true;
                detailSummaryTextarea.readOnly = true;
                detailUiSelect.disabled = true;
                saveTaskBtn.style.display = 'none';
            } else { // Active task
                completeTaskBtn.style.display = 'inline-block';
                addMslEntryFormDiv.style.display = 'block';
                detailTitleInput.readOnly = false;
                detailDueInput.readOnly = false;
                detailSummaryTextarea.readOnly = false;
                detailUiSelect.disabled = false;
                saveTaskBtn.style.display = 'inline-block';
            }
            loadMslEntries(taskId);
        } catch (error) {
            console.error('Failed to load task details:', error);
            taskDetailContentDiv.innerHTML = '<p>Error loading task details.</p>';
        }
    }

    function clearTaskDetails() {
        selectedTaskId = null;
        taskDetailFormDiv.style.display = 'none';
        addMslEntryFormDiv.style.display = 'none';
        taskDetailContentDiv.innerHTML = '<p>Select a task to see details.</p>';
        mslLogEntriesDiv.innerHTML = '';
        detailTitleInput.value = '';
        detailDueInput.value = '';
        detailSummaryTextarea.value = '';
        detailUiSelect.value = '0';
    }

    viewActiveTasksBtn.addEventListener('click', () => {
        currentTaskView = 'active';
        viewActiveTasksBtn.classList.add('active-view');
        viewCompletedTasksBtn.classList.remove('active-view');
        clearTaskDetails();
        loadTasks();
    });

    viewCompletedTasksBtn.addEventListener('click', () => {
        currentTaskView = 'completed';
        viewCompletedTasksBtn.classList.add('active-view');
        viewActiveTasksBtn.classList.remove('active-view');
        clearTaskDetails();
        loadTasks();
    });

    async function loadMslEntries(taskId) {
        try {
            const entries = await fetchAPI(`${MSL_API_BASE_PATH}/msl_entries/${taskId}`); // Use base path
            mslLogEntriesDiv.innerHTML = '';
            if (entries.length === 0) {
                mslLogEntriesDiv.innerHTML = '<p>No MSL entries yet.</p>';
                return;
            }
            entries.forEach(entry => {
                const entryDiv = document.createElement('div');
                entryDiv.classList.add('msl-entry');
                const date = new Date(entry.Date).toLocaleString();
                entryDiv.innerHTML = `
                    <div class="meta">${date} - ${entry.Submitter_FullName || entry.Submitter_Username}</div>
                    <div class="text">${entry.Text.replace(/\n/g, '<br>')}</div>
                `;
                mslLogEntriesDiv.appendChild(entryDiv);
            });
        } catch (error) {
            console.error('Failed to load MSL entries:', error);
        }
    }

    addTaskBtn.addEventListener('click', async () => {
        const title = newTaskTitleInput.value.trim();
        if (!title) {
            alert('Task title cannot be empty.');
            return;
        }
        try {
            await fetchAPI(`${MSL_API_BASE_PATH}/task`, { // Use base path
                method: 'POST',
                body: JSON.stringify({ Title: title })
            });
            newTaskTitleInput.value = '';
            loadTasks();
        } catch (error) {
            console.error('Failed to add task:', error);
        }
    });
    newTaskTitleInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            addTaskBtn.click();
        }
    });

    saveTaskBtn.addEventListener('click', async () => {
        if (!selectedTaskId) return;
        const taskData = {
            Title: detailTitleInput.value,
            Summary: detailSummaryTextarea.value,
            UI: detailUiSelect.value,
            Due: detailDueInput.value ? new Date(detailDueInput.value).toISOString() : null
        };
        try {
            await fetchAPI(`${MSL_API_BASE_PATH}/task/${selectedTaskId}`, { // Use base path
                method: 'PUT',
                body: JSON.stringify(taskData)
            });
            alert('Task updated successfully!');
            loadTasks();
        } catch (error) {
            console.error('Failed to update task:', error);
        }
    });

    completeTaskBtn.addEventListener('click', async () => {
        if (!selectedTaskId) return;
        if (!confirm('Are you sure you want to complete this task?')) return;
        try {
            await fetchAPI(`${MSL_API_BASE_PATH}/task/${selectedTaskId}/complete`, { method: 'POST' }); // Use base path
            alert('Task marked as complete!');
            clearTaskDetails();
            loadTasks();
        } catch (error) {
            console.error('Failed to complete task:', error);
        }
    });

    addMslBtn.addEventListener('click', async () => {
        if (!selectedTaskId) return;
        const text = newMslTextInput.value.trim();
        if (!text) {
            alert('MSL entry text cannot be empty.');
            return;
        }
        try {
            await fetchAPI(`${MSL_API_BASE_PATH}/msl_entry`, { // Use base path
                method: 'POST',
                body: JSON.stringify({ TaskID: selectedTaskId, Text: text })
            });
            newMslTextInput.value = '';
            loadMslEntries(selectedTaskId);
        } catch (error) {
            console.error('Failed to add MSL entry:', error);
        }
    });
    newMslTextInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            addMslBtn.click();
        }
    });

    document.querySelectorAll('.filter-btn').forEach(button => {
        button.addEventListener('click', (e) => {
            currentFilter = e.target.dataset.filter;
            document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active-filter'));
            e.target.classList.add('active-filter');
            loadTasks();
        });
    });

    // Initial load
    if (viewActiveTasksBtn) viewActiveTasksBtn.classList.add('active-view'); // Set default view button state
    if (document.querySelector('.filter-btn[data-filter="Filter_UI"]')) { // Set default filter button state
        document.querySelector('.filter-btn[data-filter="Filter_UI"]').classList.add('active-filter');
    }
    loadTasks();
});
