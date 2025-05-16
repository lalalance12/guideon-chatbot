import React, { useState } from 'react';
import { Course } from '../services/courseService';

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

  return (
    <div className="bg-white rounded-lg shadow-md p-6 mb-4 border border-gray-200">
      <div className="flex gap-8 items-start">
      <h1 className="text-lg font-semibold">
        <a href={course.url} target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:text-indigo-800">
          {course.title}
        </a>
      </h1>
      <span className={`px-3 py-1 rounded-full text-white text-sm font-medium ${isFree ? 'bg-green-500' : 'bg-orange-500'}`}>
          {course.price}
        </span>
      </div>
      <p className="text-gray-600 mb-2">Provider: {course.provider}</p>
      <p className="text-gray-600">Rating: {course.rating.toFixed(1)}/5</p>
      <p className="text-gray-700 mb-4">{course.description}</p>
      
      {!showFeedback && (
        <div className="flex gap-4">
          <button
            onClick={() => handleCompletionStatus('completed')}
            className="px-4 py-2 bg-green-500 text-white rounded-md hover:bg-green-600 transition-colors"
          >
            I Completed the Course
          </button>
          <button
            onClick={() => handleCompletionStatus('not_completed')}
            className="px-4 py-2 bg-red-500 text-white rounded-md hover:bg-red-600 transition-colors"
          >
            I Can't Complete the Course
          </button>
        </div>
      )}

      {showFeedback && completionStatus !== 'not_started' && (
        <div className="mt-4">
          <h4 className="text-lg font-medium mb-3">
            {completionStatus === 'completed' 
              ? "How was your experience with the course?" 
              : "Why couldn't you complete the course?"}
          </h4>
          <div className="space-y-2">
            {feedbackQuestions[completionStatus].map((answer: string, index: number) => (
              <button
                key={index}
                className="w-full p-3 text-left bg-gray-50 hover:bg-gray-100 rounded-md transition-colors"
                onClick={() => {
                  setShowFeedback(false);
                  setCompletionStatus('not_started');
                }}
              >
                {answer}
              </button>
            ))}
          </div>
          <button
            onClick={() => {
              setShowFeedback(false);
              setCompletionStatus('not_started');
            }}
            className="mt-4 px-4 py-2 bg-gray-500 text-white rounded-md hover:bg-gray-600 transition-colors"
          >
            Back to Course
          </button>
        </div>
      )}
    </div>
  );
};

export default CourseCard; 