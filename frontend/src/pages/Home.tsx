import React from 'react';

const Home: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-100">
      <section className="py-12 px-4 max-w-6xl mx-auto">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-800 mb-4">Welcome to Our Platform</h1>
          <p className="text-xl text-gray-600">Your one-stop solution for all your needs</p>
          <button className="mt-6 px-6 py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition-colors">
            Get Started
          </button>
        </div>
      </section>

      <section className="py-12 px-4 bg-white">
        <h2 className="text-3xl font-bold text-center mb-8">Our Features</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-6xl mx-auto">
          <div className="bg-gray-50 p-6 rounded-lg shadow">
            <h3 className="text-xl font-semibold mb-3">Easy to Use</h3>
            <p className="text-gray-600">Our intuitive interface makes navigation simple and straightforward.</p>
          </div>
          <div className="bg-gray-50 p-6 rounded-lg shadow">
            <h3 className="text-xl font-semibold mb-3">Fast & Reliable</h3>
            <p className="text-gray-600">Built with performance in mind to ensure quick response times.</p>
          </div>
          <div className="bg-gray-50 p-6 rounded-lg shadow">
            <h3 className="text-xl font-semibold mb-3">Secure</h3>
            <p className="text-gray-600">Your data is protected with state-of-the-art security measures.</p>
          </div>
        </div>
      </section>

      <section className="py-12 px-4 max-w-4xl mx-auto">
        <h2 className="text-3xl font-bold text-center mb-6">About Us</h2>
        <p className="text-gray-600 text-center">
          We are dedicated to providing the best experience for our users. Our team works tirelessly 
          to ensure that our platform meets your needs and exceeds your expectations.
        </p>
      </section>
    </div>
  );
};

export default Home;