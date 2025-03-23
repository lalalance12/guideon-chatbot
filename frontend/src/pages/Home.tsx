import React from "react";
import { useNavigate } from "react-router-dom";
import {
  BookOpen,
  Compass,
  MessageSquare,
  ArrowRight,
  GraduationCap,
} from "lucide-react";

const Home: React.FC = () => {
  const navigate = useNavigate();

  const handleStartChat = () => {
    navigate("/chat");
  };

  return (
    <div className="min-h-screen bg-gradient-main overflow-hidden">
      <header className="py-6 px-4 bg-white shadow-sm relative z-10">
        <div className="max-w-6xl mx-auto flex justify-between items-center">
          <div className="flex items-center">
            <h1 className="text-2xl font-bold text-indigo-600">Guideon</h1>
          </div>
          <button onClick={handleStartChat} className="btn btn-primary">
            Start Chatting
          </button>
        </div>
      </header>

      <section className="relative py-20 px-4 overflow-hidden">
        <div className="absolute inset-0 bg-indigo-50 opacity-60"></div>
        <div className="absolute right-0 top-0 w-1/3 h-full bg-gradient-to-l from-indigo-100 to-transparent"></div>
        <div className="absolute left-0 bottom-0 w-1/2 h-1/2 bg-gradient-to-t from-blue-50 to-transparent"></div>

        <div className="max-w-6xl mx-auto relative z-10">
          <div className="text-center lg:text-left lg:flex items-center justify-between">
            <div className="lg:w-1/2 mb-10 lg:mb-0">
              <h1 className="text-5xl font-bold text-gray-800 mb-6 leading-tight">
                Meet <span className="text-indigo-600">Guideon</span>,
                <br />
                Your AI Learning Guide
              </h1>
              <p className="text-xl text-gray-600 max-w-2xl mx-auto lg:mx-0 mb-8">
                Your intelligent learning companion designed to guide students,
                scholars, and lifelong learners on their educational journey.
              </p>
              <button
                onClick={handleStartChat}
                className="btn btn-primary text-lg px-8 py-4 shadow-lg inline-flex items-center gap-2"
              >
                Start Learning Now
                <ArrowRight size={18} />
              </button>
            </div>
            <div className="lg:w-1/2 flex justify-center">
              <div className="w-80 h-80 relative">
                <div
                  className="absolute inset-0 bg-indigo-600 rounded-full opacity-10 animate-pulse delay-150"
                  style={{ animationDuration: "3s" }}
                ></div>
                <div
                  className="absolute inset-4 bg-indigo-600 rounded-full opacity-20 animate-pulse"
                  style={{ animationDuration: "3s" }}
                ></div>
                <div className="absolute inset-8 bg-indigo-500 rounded-full opacity-70 flex items-center justify-center">
                  <GraduationCap size={100} className="text-white" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="py-20 px-4 bg-white relative">
        <div className="absolute inset-0 bg-gradient-to-b from-indigo-50 to-white opacity-50 h-32"></div>
        <div className="max-w-6xl mx-auto relative">
          <h2 className="text-3xl font-bold text-center mb-16">
            How Guideon Helps You Learn
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-10">
            <div className="bg-white p-8 rounded-xl shadow-md hover:shadow-lg transition-smooth border border-gray-100 relative overflow-hidden group">
              <div className="absolute inset-0 bg-gradient-to-r from-indigo-50 to-transparent opacity-0 group-hover:opacity-100 transition-smooth"></div>
              <div className="bg-indigo-100 p-3 rounded-lg inline-block mb-6 relative">
                <Compass className="text-indigo-600" size={28} />
              </div>
              <h3 className="text-2xl font-semibold mb-4 text-indigo-600 relative">
                Personalized Learning
              </h3>
              <p className="text-gray-600 relative">
                Guideon adapts to your learning style and provides tailored
                guidance to optimize your educational experience.
              </p>
            </div>
            <div className="bg-white p-8 rounded-xl shadow-md hover:shadow-lg transition-smooth border border-gray-100 relative overflow-hidden group">
              <div className="absolute inset-0 bg-gradient-to-r from-indigo-50 to-transparent opacity-0 group-hover:opacity-100 transition-smooth"></div>
              <div className="bg-indigo-100 p-3 rounded-lg inline-block mb-6 relative">
                <BookOpen className="text-indigo-600" size={28} />
              </div>
              <h3 className="text-2xl font-semibold mb-4 text-indigo-600 relative">
                Course Recommendations
              </h3>
              <p className="text-gray-600 relative">
                Get expert recommendations on the best courses and learning
                paths based on your interests and career goals.
              </p>
            </div>
            <div className="bg-white p-8 rounded-xl shadow-md hover:shadow-lg transition-smooth border border-gray-100 relative overflow-hidden group">
              <div className="absolute inset-0 bg-gradient-to-r from-indigo-50 to-transparent opacity-0 group-hover:opacity-100 transition-smooth"></div>
              <div className="bg-indigo-100 p-3 rounded-lg inline-block mb-6 relative">
                <MessageSquare className="text-indigo-600" size={28} />
              </div>
              <h3 className="text-2xl font-semibold mb-4 text-indigo-600 relative">
                24/7 Assistance
              </h3>
              <p className="text-gray-600 relative">
                Access learning support whenever you need it. Guideon is always
                available to answer questions and provide guidance.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="py-20 px-4 bg-gradient-to-b from-white to-indigo-50">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-8">
            Who Can Benefit from Guideon
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mt-10">
            <div className="bg-white p-6 rounded-lg shadow-md hover:shadow-lg transition-smooth border border-gray-100 hover:border-indigo-100">
              <h3 className="text-xl font-semibold mb-3 text-indigo-600 flex items-center gap-2">
                <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0">
                  <span className="text-indigo-600 font-bold">1</span>
                </div>
                University Students
              </h3>
              <p className="text-gray-600 ml-10">
                Get help with course selections, research papers, and
                understanding complex topics in your field of study.
              </p>
            </div>
            <div className="bg-white p-6 rounded-lg shadow-md hover:shadow-lg transition-smooth border border-gray-100 hover:border-indigo-100">
              <h3 className="text-xl font-semibold mb-3 text-indigo-600 flex items-center gap-2">
                <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0">
                  <span className="text-indigo-600 font-bold">2</span>
                </div>
                Scholars & Researchers
              </h3>
              <p className="text-gray-600 ml-10">
                Explore new research areas, find relevant publications, and get
                assistance with academic writing.
              </p>
            </div>
            <div className="bg-white p-6 rounded-lg shadow-md hover:shadow-lg transition-smooth border border-gray-100 hover:border-indigo-100">
              <h3 className="text-xl font-semibold mb-3 text-indigo-600 flex items-center gap-2">
                <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0">
                  <span className="text-indigo-600 font-bold">3</span>
                </div>
                Up-Skillers
              </h3>
              <p className="text-gray-600 ml-10">
                Discover the most in-demand skills for your career path and find
                the best resources to master them.
              </p>
            </div>
            <div className="bg-white p-6 rounded-lg shadow-md hover:shadow-lg transition-smooth border border-gray-100 hover:border-indigo-100">
              <h3 className="text-xl font-semibold mb-3 text-indigo-600 flex items-center gap-2">
                <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0">
                  <span className="text-indigo-600 font-bold">4</span>
                </div>
                Lifelong Learners
              </h3>
              <p className="text-gray-600 ml-10">
                Pursue your passions and interests with guided learning
                experiences tailored to your goals.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="py-16 px-4 bg-indigo-600 text-white">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl font-bold mb-6">
            Ready to Accelerate Your Learning?
          </h2>
          <p className="text-indigo-100 mb-8 max-w-2xl mx-auto">
            Start your educational journey with Guideon today and discover a
            personalized approach to mastering new skills and knowledge.
          </p>
          <button
            onClick={handleStartChat}
            className="px-8 py-4 bg-white text-indigo-600 rounded-lg hover:bg-indigo-50 transition-smooth font-bold text-lg shadow-lg"
          >
            Chat with Guideon Now
          </button>
        </div>
      </section>

      <footer className="bg-indigo-900 text-white py-10">
        <div className="max-w-6xl mx-auto px-4 text-center">
          <p className="mb-4">© 2023 Guideon Learning Assistant</p>
          <p className="text-indigo-200">
            Powered by advanced AI to help you achieve your learning goals
          </p>
        </div>
      </footer>
    </div>
  );
};

export default Home;
