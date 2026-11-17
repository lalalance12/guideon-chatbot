import React from "react";
import { ACCESS_TOKEN } from "../constants";

interface UserCourseCardProps {
  course: any;
  userCourse: any;
  onComplete?: () => void;
}

const UserCourseCard: React.FC<UserCourseCardProps> = ({ course, userCourse, onComplete }) => {
  const isFree = course.price && course.price.toLowerCase() === "free";

  const handleCompleteCourse = async () => {
    if (!window.confirm("Are you sure you want to mark this course as completed?")) {
      return;
    }
    try {
      const token = localStorage.getItem(ACCESS_TOKEN);
      const response = await fetch("/api/complete-course/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ user_course_id: userCourse.id }),
      });
      const data = await response.json();
      if (response.ok) {
        alert("Course marked as completed!");
        if (onComplete) onComplete();
      } else {
        alert(data.error || "Failed to complete course.");
      }
    } catch (error) {
      alert("An error occurred while completing the course.");
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
        <span className={`px-3 py-1 rounded-full text-white text-sm font-medium ${isFree ? 'bg-green-500' : 'bg-orange-500'}`}>{course.price}</span>
      </div>
      <p className="text-gray-600 mb-2">Provider: {course.provider}</p>
      <p className="text-gray-600">Rating: {course.rating ? course.rating.toFixed(1) : 'N/A'}/5</p>
      <p className="text-gray-600">Enrolled: {new Date(userCourse.learned_at).toLocaleDateString()}</p>
      {course.description && course.description.length > 450 ? (
        <p className="text-gray-700 mb-4">{course.description.slice(0, 450)}...</p>
      ) : (
        <p className="text-gray-700 mb-4">{course.description}</p>
      )}
      <div className="flex justify-end">
        {userCourse.status !== "completed" && (
          <button
            className="px-4 py-2 bg-indigo-400 text-white rounded-md hover:bg-indigo-600 transition-colors"
            onClick={handleCompleteCourse}
          >
            Complete this course
          </button>
        )}
      </div>
    </div>
  );
};

export default UserCourseCard;