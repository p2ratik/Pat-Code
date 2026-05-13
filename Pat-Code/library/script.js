// Library Management System Data Store
let books = JSON.parse(localStorage.getItem('libraryBooks')) || [];
let currentEditId = null;

// DOM Elements
const addBookForm = document.getElementById('addBookForm');
const editBookForm = document.getElementById('editBookForm');
const searchInput = document.getElementById('searchInput');
const filterGenre = document.getElementById('filterGenre');
const searchBtn = document.getElementById('searchBtn');
const editModal = document.getElementById('editModal');
const closeModal = document.getElementById('closeModal');
const cancelEdit = document.getElementById('cancelEdit');
const bookTableBody = document.getElementById('bookTableBody');
const emptyState = document.getElementById('emptyState');

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    // Set current year in footer
    document.getElementById('currentYear').textContent = new Date().getFullYear();
    
    // Render initial book list
    renderBooks(books);
    updateStats();
    
    // Set up form submission
    addBookForm.addEventListener('submit', handleAddBook);
    editBookForm.addEventListener('submit', handleEditBook);
    
    // Set up search functionality
    searchBtn.addEventListener('click', handleSearch);
    searchInput.addEventListener('keyup', function(event) {
        if (event.key === 'Enter') {
            handleSearch();
        }
    });
    filterGenre.addEventListener('change', handleSearch);
    
    // Set up modal controls
    closeModal.addEventListener('click', closeEditModal);
    cancelEdit.addEventListener('click', closeEditModal);
    
    // Close modal when clicking outside
    window.addEventListener('click', function(event) {
        if (event.target === editModal) {
            closeEditModal();
        }
    });
});

// Handle adding a new book
function handleAddBook(event) {
    event.preventDefault();
    
    const book = {
        id: Date.now().toString(),
        title: document.getElementById('bookTitle').value.trim(),
        author: document.getElementById('bookAuthor').value.trim(),
        isbn: document.getElementById('bookIsbn').value.trim(),
        genre: document.getElementById('bookGenre').value,
        year: document.getElementById('bookYear').value,
        quantity: parseInt(document.getElementById('bookQuantity').value) || 1,
        addedDate: new Date().toLocaleDateString(),
        available: true
    };
    
    books.push(book);
    saveToStorage();
    renderBooks(books);
    updateStats();
    
    // Show success message
    showNotification('Book added successfully!', 'success');
    
    // Reset form
    addBookForm.reset();
    document.getElementById('bookQuantity').value = 1;
}

// Handle editing an existing book
function handleEditBook(event) {
    event.preventDefault();
    
    const index = books.findIndex(book => book.id === currentEditId);
    if (index !== -1) {
        books[index].title = document.getElementById('editTitle').value.trim();
        books[index].author = document.getElementById('editAuthor').value.trim();
        books[index].isbn = document.getElementById('editIsbn').value.trim();
        books[index].genre = document.getElementById('editGenre').value;
        books[index].year = document.getElementById('editYear').value;
        books[index].quantity = parseInt(document.getElementById('editQuantity').value) || 1;
        
        saveToStorage();
        renderBooks(books);
        updateStats();
        
        showNotification('Book updated successfully!', 'success');
        closeEditModal();
    }
}

// Delete a book
function deleteBook(id, title) {
    if (confirm(`Are you sure you want to delete "${title}"?`)) {
        books = books.filter(book => book.id !== id);
        saveToStorage();
        renderBooks(books);
        updateStats();
        showNotification('Book deleted successfully!', 'success');
    }
}

// Borrow/Return functionality
function toggleAvailability(id) {
    const book = books.find(book => book.id === id);
    if (book) {
        book.available = !book.available;
        saveToStorage();
        renderBooks(books);
        updateStats();
        
        const action = book.available ? 'returned' : 'borrowed';
        showNotification(`Book ${action} successfully!`, 'success');
    }
}

// Open edit modal
function openEditModal(id) {
    const book = books.find(book => book.id === id);
    if (book) {
        currentEditId = id;
        document.getElementById('editTitle').value = book.title;
        document.getElementById('editAuthor').value = book.author;
        document.getElementById('editIsbn').value = book.isbn;
        document.getElementById('editGenre').value = book.genre;
        document.getElementById('editYear').value = book.year;
        document.getElementById('editQuantity').value = book.quantity;
        
        editModal.style.display = 'block';
        document.getElementById('editTitle').focus();
    }
}

// Close edit modal
function closeEditModal() {
    editModal.style.display = 'none';
    currentEditId = null;
    editBookForm.reset();
}

// Handle search and filter
function handleSearch() {
    const searchTerm = searchInput.value.toLowerCase().trim();
    const selectedGenre = filterGenre.value;
    
    let filteredBooks = books;
    
    // Filter by search term
    if (searchTerm) {
        filteredBooks = filteredBooks.filter(book => 
            book.title.toLowerCase().includes(searchTerm) ||
            book.author.toLowerCase().includes(searchTerm) ||
            book.isbn.includes(searchTerm)
        );
    }
    
    // Filter by genre
    if (selectedGenre) {
        filteredBooks = filteredBooks.filter(book => book.genre === selectedGenre);
    }
    
    renderBooks(filteredBooks);
}

// Render books to the table
function renderBooks(booksToRender) {
    bookTableBody.innerHTML = '';
    
    if (booksToRender.length === 0) {
        emptyState.style.display = 'block';
    } else {
        emptyState.style.display = 'none';
        
        booksToRender.forEach(book => {
            const row = document.createElement('tr');
            
            row.innerHTML = `
                <td><strong>${escapeHtml(book.title)}</strong></td>
                <td>${escapeHtml(book.author)}</td>
                <td>
                    <span class="genre-badge" style="
                        display: inline-block;
                        padding: 4px 12px;
                        border-radius: 20px;
                        font-size: 0.85rem;
                        font-weight: 500;
                        background: ${getGenreColor(book.genre)};
                        color: white;
                    ">${book.genre || 'Other'}</span>
                </td>
                <td>${book.year || '-'}</td>
                <td>${book.isbn || '-'}</td>
                <td class="quantity-col">${book.quantity}</td>
                <td class="actions-col">
                    <div class="action-buttons">
                        <button class="btn btn-sm btn-warning" onclick="openEditModal('${book.id}')" title="Edit">
                            ✏️
                        </button>
                        <button class="btn btn-sm ${book.available ? 'btn-danger' : 'btn-secondary'}" 
                                onclick="toggleAvailability('${book.id}')"
                                title="${book.available ? 'Mark as borrowed' : 'Mark as returned'}">
                            ${book.available ? '📤' : '📥'}
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="deleteBook('${book.id}', '${escapeHtml(book.title)}')" title="Delete">
                            🗑️
                        </button>
                    </div>
                </td>
            `;
            
            bookTableBody.appendChild(row);
        });
    }
    
    document.getElementById('bookCount').textContent = `${booksToRender.length} ${booksToRender.length === 1 ? 'book' : 'books'}`;
}

// Update statistics
function updateStats() {
    const uniqueAuthors = [...new Set(books.map(book => book.author.toLowerCase()))].length;
    const uniqueGenres = [...new Set(books.map(book => book.genre).filter(g => g))].length;
    const totalQuantity = books.reduce((sum, book) => sum + book.quantity, 0);
    const availableCount = books.filter(book => book.available).length;
    
    document.getElementById('totalBooks').textContent = books.length;
    document.getElementById('totalAuthors').textContent = uniqueAuthors;
    document.getElementById('availableBooks').textContent = availableCount;
    document.getElementById('totalGenres').textContent = uniqueGenres;
}

// Save to localStorage
function saveToStorage() {
    localStorage.setItem('libraryBooks', JSON.stringify(books));
}

// Show notification
function showNotification(message, type = 'success') {
    // Remove existing notification
    const existing = document.querySelector('.notification');
    if (existing) {
        existing.remove();
    }
    
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 25px;
        border-radius: 10px;
        color: white;
        font-weight: 600;
        z-index: 1001;
        animation: slideIn 0.5s ease;
        background: ${type === 'success' ? '#4CAF50' : '#2196F3'};
        box-shadow: 0 5px 20px rgba(0, 0, 0, 0.2);
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.5s ease';
        setTimeout(() => notification.remove(), 500);
    }, 3000);
}

// Helper function to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Get color based on genre
function getGenreColor(genre) {
    const colors = {
        'Fiction': '#667eea',
        'Non-Fiction': '#764ba2',
        'Science': '#11998e',
        'History': '#e67e22',
        'Biography': '#3498db',
        'Technology': '#e74c3c',
        'Art': '#f39c12',
        'Philosophy': '#9b59b6',
        'Other': '#7f8c8d'
    };
    return colors[genre] || colors['Other'];
}

// Add CSS animations for notifications
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
`;
document.head.appendChild(style);