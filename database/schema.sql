CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('customer', 'admin') NOT NULL DEFAULT 'customer',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE paintings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    painting_code VARCHAR(20) NOT NULL UNIQUE,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    price DECIMAL(10,2) NOT NULL,
    image_path VARCHAR(255),
    status ENUM('available', 'sold') NOT NULL DEFAULT 'available',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (price >= 0)
);

CREATE TABLE painting_orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    painting_id INT NOT NULL,
    status ENUM('placed', 'cancelled') NOT NULL DEFAULT 'placed',
    ordered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cancelled_at TIMESTAMP NULL,

    FOREIGN KEY (customer_id) REFERENCES users(id),
    FOREIGN KEY (painting_id) REFERENCES paintings(id)
);

CREATE TABLE wall_painting_bookings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    booking_date DATE NOT NULL UNIQUE,
    area_sqft INT NOT NULL,
    address TEXT NOT NULL,
    rate_per_sqft DECIMAL(10,2) NOT NULL DEFAULT 150.00,
    total_price DECIMAL(12,2)
        GENERATED ALWAYS AS (area_sqft * rate_per_sqft) STORED,
    status ENUM(
        'requested',
        'confirmed',
        'declined',
        'cancelled'
    ) NOT NULL DEFAULT 'requested',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (customer_id) REFERENCES users(id),
    CHECK (area_sqft BETWEEN 10 AND 500),
    CHECK (rate_per_sqft >= 0)
);

CREATE TABLE pottery_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    item_name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE pottery_glazes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    glaze_name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE pottery_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    item_id INT NOT NULL,
    glaze_id INT NOT NULL,
    quantity INT NOT NULL,
    needed_by DATE NOT NULL,
    status ENUM(
        'requested',
        'accepted',
        'declined',
        'cancelled'
    ) NOT NULL DEFAULT 'requested',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (customer_id) REFERENCES users(id),
    FOREIGN KEY (item_id) REFERENCES pottery_items(id),
    FOREIGN KEY (glaze_id) REFERENCES pottery_glazes(id),
    CHECK (quantity BETWEEN 1 AND 12)
);