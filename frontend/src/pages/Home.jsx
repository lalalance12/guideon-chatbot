import React from 'react';

const Home = () => {
    return (
        <div className="home-container">
            <section className="hero-section">
                <div className="hero-content">
                    <h1>Welcome to Our Platform</h1>
                    <p>Your one-stop solution for all your needs</p>
                    <button className="cta-button">Get Started</button>
                </div>
            </section>

            <section className="features-section">
                <h2>Our Features</h2>
                <div className="features-grid">
                    <div className="feature-card">
                        <h3>Easy to Use</h3>
                        <p>Our intuitive interface makes navigation simple and straightforward.</p>
                    </div>
                    <div className="feature-card">
                        <h3>Fast & Reliable</h3>
                        <p>Built with performance in mind to ensure quick response times.</p>
                    </div>
                    <div className="feature-card">
                        <h3>Secure</h3>
                        <p>Your data is protected with state-of-the-art security measures.</p>
                    </div>
                </div>
            </section>

            <section className="about-section">
                <h2>About Us</h2>
                <p>We are dedicated to providing the best experience for our users. Our team works tirelessly to ensure that our platform meets your needs and exceeds your expectations.</p>
            </section>
        </div>
    );
};

export default Home;