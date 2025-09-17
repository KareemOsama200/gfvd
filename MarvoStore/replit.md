# replit.md

## Overview

Marvo is an Arabic e-commerce web application for clothing and fashion items. The application features a product catalog, shopping cart functionality, and an admin panel for product management. The interface is designed with RTL (right-to-left) support for Arabic content and uses a dark theme with yellow and blue accent colors. The application allows users to browse products, view detailed product information, add items to their cart, and provides administrators with tools to manage the product inventory.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
- **Template Engine**: Jinja2 templates with Flask
- **CSS Framework**: Bootstrap 5.3.0 with custom CSS variables for theming
- **Internationalization**: RTL layout support for Arabic language
- **Icons**: Font Awesome 6.0.0 for consistent iconography
- **Theme**: Dark theme with custom color scheme (yellow primary, blue accents)

### Backend Architecture
- **Framework**: Flask web framework
- **Form Handling**: Flask-WTF for form processing and CSRF protection
- **File Upload**: Support for product image uploads with enctype="multipart/form-data"
- **Security**: CSRF token implementation across all forms
- **Routing**: RESTful URL patterns for product management and cart operations

### Data Models
- **Product Model**: Contains name, description, price, stock, category, and image_url fields
- **Cart System**: Shopping cart with item management including size and color variants
- **Product Categories**: Categorized products (shirts, pants, shoes) with Arabic translations
- **Product Variants**: Support for size and color options per product

### User Interface Components
- **Product Catalog**: Grid-based product display with image, name, description, and price
- **Product Detail View**: Detailed product page with variant selection (size/color)
- **Shopping Cart**: Cart management with quantity display and item removal
- **Admin Panel**: Product management interface with table view and CRUD operations
- **Navigation**: Responsive navbar with brand identity and navigation links

### Authentication & Authorization
- **Admin Access**: Role-based access control for admin panel functionality
- **Session Management**: User session handling for cart persistence

## External Dependencies

### Frontend Libraries
- **Bootstrap 5.3.0**: UI framework for responsive design and components
- **Font Awesome 6.0.0**: Icon library for user interface elements

### Backend Dependencies
- **Flask**: Primary web framework
- **Flask-WTF**: Form handling and CSRF protection
- **Jinja2**: Template engine (included with Flask)

### File Storage
- **Static File Serving**: Local file storage for product images in static directory
- **Image Upload**: File upload handling for product image management

### Database
- **Data Storage**: Database system for storing product information, cart items, and user data (specific database technology not specified in templates but likely SQLAlchemy-based)