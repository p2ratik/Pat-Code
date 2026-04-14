document.addEventListener('DOMContentLoaded', function() {
    const todoInput = document.getElementById('todoInput');
    const addBtn = document.getElementById('addBtn');
    const todoList = document.getElementById('todoList');

    // Load todos from localStorage if available
    let todos = JSON.parse(localStorage.getItem('todos')) || [];

    // Function to render todos
    function renderTodos() {
        todoList.innerHTML = '';
        todos.forEach((todo, index) => {
            const li = document.createElement('li');
            li.className = `todo-item ${todo.completed ? 'completed' : ''}`;
            
            li.innerHTML = `
                <span class="todo-text">${todo.text}</span>
                <div class="todo-actions">
                    <button class="completeBtn" data-index="${index}">
                        ${todo.completed ? 'Undo' : 'Complete'}
                    </button>
                    <button class="deleteBtn" data-index="${index}">Delete</button>
                </div>
            `;
            
            todoList.appendChild(li);
        });
        
        // Save to localStorage
        localStorage.setItem('todos', JSON.stringify(todos));
    }

    // Add todo
    addBtn.addEventListener('click', function() {
        const text = todoInput.value.trim();
        if (text) {
            todos.push({
                text: text,
                completed: false
            });
            todoInput.value = '';
            renderTodos();
        }
    });

    // Allow Enter key to add todo
    todoInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            addBtn.click();
        }
    });

    // Handle todo actions (complete/delete)
    todoList.addEventListener('click', function(e) {
        if (e.target.classList.contains('completeBtn')) {
            const index = parseInt(e.target.getAttribute('data-index'));
            todos[index].completed = !todos[index].completed;
            renderTodos();
        } else if (e.target.classList.contains('deleteBtn')) {
            const index = parseInt(e.target.getAttribute('data-index'));
            todos.splice(index, 1);
            renderTodos();
        }
    });

    // Initial render
    renderTodos();
});