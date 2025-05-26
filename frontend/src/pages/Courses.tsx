import React, { useState, useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ACCESS_TOKEN } from "../constants";
import UserCourseCard from "../components/UserCourseCard";

const TABS = [
  { label: "Ongoing", value: "in_progress" },
  { label: "Completed", value: "completed" },
];

const Courses: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const params = new URLSearchParams(location.search);
  const tab = params.get("tab") || "in_progress";

  const [courses, setCourses] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchCourses = async (status: string) => {
    setLoading(true);
    const token = localStorage.getItem(ACCESS_TOKEN);
    const response = await fetch(`/api/user-courses/?status=${status}`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    const data = await response.json();
    setCourses(data);
    setLoading(false);
  };

  // Add a reload handler for child
  const handleReload = () => {
    fetchCourses(tab);
  };

  useEffect(() => {
    fetchCourses(tab);
    // eslint-disable-next-line
  }, [tab]);

  const handleTabChange = (value: string) => {
    navigate(`/courses?tab=${value}`);
  };

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-4">Courses</h1>
      <div className="flex gap-4 mb-6">
        {TABS.map((t) => (
          <button
            key={t.value}
            className={`px-4 py-2 rounded-md font-medium transition-colors ${
              tab === t.value
                ? "bg-indigo-500 text-white"
                : "bg-gray-200 text-gray-700 hover:bg-gray-300"
            }`}
            onClick={() => handleTabChange(t.value)}
          >
            {t.label}
          </button>
        ))}
      </div>
      {loading ? (
        <div>Loading...</div>
      ) : courses.length === 0 ? (
        <div className="mt-4">No courses found.</div>
      ) : (
        <div className="grid gap-4">
          {courses.map((uc) => (
            <UserCourseCard key={uc.id} course={uc.course} userCourse={uc} onComplete={handleReload} />
          ))}
        </div>
      )}
    </div>
  );
};

export default Courses;
