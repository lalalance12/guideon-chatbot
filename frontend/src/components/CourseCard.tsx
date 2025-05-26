import React, { useState } from 'react';
import { Course } from '../services/courseService';
import { ACCESS_TOKEN } from '../constants';

interface CourseCardProps {
  course: Course;
}

const CourseCard: React.FC<CourseCardProps> = ({ course }) => {
  const [showFeedback, setShowFeedback] = useState(false);
  const [completionStatus, setCompletionStatus] = useState<'not_started' | 'completed' | 'not_completed'>('not_started');

  const handleCompletionStatus = (status: 'completed' | 'not_completed') => {
    setCompletionStatus(status);
    setShowFeedback(true);
  };

  const feedbackQuestions: Record<Exclude<typeof completionStatus, 'not_started'>, string[]> = {
    completed: [
      "The course was engaging and well-structured",
      "The course was informative but could be more interactive",
      "The course was challenging but rewarding"
    ],
    not_completed: [
      "The course was too long",
      "The course was too difficult",
      "I didn't have enough time"
    ]
  };

  // Determine if the course is free
  const isFree = course.price.toLowerCase() === 'free';

  console.log('Course data:', course); // Debug log

  const handleTakeCourse = async () => {
    if (!window.confirm("Are you sure you want to enroll in this course?")) {
      return;
    }
    try {
      const token = localStorage.getItem(ACCESS_TOKEN);
      const response = await fetch('/api/take-course/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ course })
      });
      const data = await response.json();
      if (response.ok) {
        alert('Course added to your learning path!');
      } else {
        alert(data.error || 'Failed to take course.');
      }
    } catch (error) {
      alert('An error occurred while taking the course.');
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-md p-6 mb-4 border border-gray-200">
      <div className="flex gap-6 items-center">
      <h2 className="text-lg font-semibold pb-3">
        <a href={course.url} target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:text-indigo-800">
          {course.title}
        </a>
      </h2>
      <span className={`px-3 py-1 rounded-full text-white text-sm font-medium ${isFree ? 'bg-green-500' : 'bg-orange-500'}`}>
          {course.price}
        </span>
      </div>
      <p className="text-gray-600 mb-2">Provider: {course.provider}</p>
      <p className="text-gray-600">Rating: {course.rating.toFixed(1)}/5</p>
      {course.description.length > 450 ? (
        <p className="text-gray-700 mb-4">
          {course.description.slice(0, 450)}...
        </p>
      ) : (
        <p className="text-gray-700 mb-4">{course.description}</p>
      )}
      
        <div className="flex justify-end">
          <button
            className="px-4 py-2 bg-indigo-400 text-white rounded-md hover:bg-indigo-600 transition-colors"
            onClick={handleTakeCourse}
          >
            Take this Course
          </button>
        </div>
    </div>
  );
};

export default CourseCard;