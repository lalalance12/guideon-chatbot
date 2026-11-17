import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { preferenceService, UserPreferences } from "../services/preferences";

const programmingLanguageOptions = [
  "JavaScript",
  "TypeScript",
  "Python",
  "Java",
  "C#",
  "PHP",
  "Go",
  "Ruby",
  "Swift",
  "Kotlin",
  "Rust",
  "C++",
  "C",
];

const developmentAreaOptions = [
  "Web Development",
  "Mobile Development",
  "Desktop Applications",
  "Game Development",
  "Data Science",
  "Machine Learning",
  "DevOps",
  "Blockchain",
  "Cloud Computing",
];

const Preferences: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [preferences, setPreferences] = useState<UserPreferences>({
    course_level: "all",
    programming_languages: [],
    development_areas: [],
  });

  useEffect(() => {
    const loadPreferences = async () => {
      try {
        const data = await preferenceService.getPreferences();
        setPreferences(data);
      } catch (err: any) {
        setError("Failed to load preferences");
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    loadPreferences();
  }, []);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError("");
    setSuccess(false);
    setSubmitting(true);

    try {
      await preferenceService.updatePreferences(preferences);
      setSuccess(true);
      // Redirect after successful save
      setTimeout(() => navigate("/chat"), 1500);
    } catch (err: any) {
      setError(err.response?.data?.error || "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  };

  const handleCourseLevel = (level: UserPreferences["course_level"]) => {
    setPreferences({ ...preferences, course_level: level });
  };

  const handleLanguageToggle = (language: string) => {
    setPreferences((prev) => {
      const langs = [...prev.programming_languages];
      if (langs.includes(language)) {
        return {
          ...prev,
          programming_languages: langs.filter((l) => l !== language),
        };
      } else {
        return { ...prev, programming_languages: [...langs, language] };
      }
    });
  };

  const handleAreaToggle = (area: string) => {
    setPreferences((prev) => {
      const areas = [...prev.development_areas];
      if (areas.includes(area)) {
        return { ...prev, development_areas: areas.filter((a) => a !== area) };
      } else {
        return { ...prev, development_areas: [...areas, area] };
      }
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-main flex items-center justify-center">
        <div className="animate-pulse text-indigo-600 text-xl">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-main py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto bg-white rounded-xl shadow-lg p-8">
        <h1 className="text-3xl font-bold text-center text-indigo-600 mb-8">
          Your Learning Preferences
        </h1>

        {error && (
          <div className="bg-red-50 text-red-600 p-3 rounded-lg mb-6">
            {error}
          </div>
        )}

        {success && (
          <div className="bg-green-50 text-green-600 p-3 rounded-lg mb-6">
            Preferences saved successfully! Redirecting...
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-8">
          {/* Course Level Selection */}
          <div>
            <h2 className="text-xl font-semibold text-gray-800 mb-4">
              What level of courses are you looking for?
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              {["beginner", "intermediate", "advanced", "all"].map((level) => (
                <div
                  key={level}
                  onClick={() =>
                    handleCourseLevel(level as UserPreferences["course_level"])
                  }
                  className={`px-4 py-3 rounded-lg border-2 cursor-pointer transition-colors ${
                    preferences.course_level === level
                      ? "border-indigo-600 bg-indigo-50 text-indigo-700"
                      : "border-gray-200 hover:border-indigo-300"
                  }`}
                >
                  <div className="font-medium capitalize">{level}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Programming Languages */}
          <div>
            <h2 className="text-xl font-semibold text-gray-800 mb-4">
              Which programming languages are you interested in?
            </h2>
            <div className="flex flex-wrap gap-3">
              {programmingLanguageOptions.map((language) => (
                <div
                  key={language}
                  onClick={() => handleLanguageToggle(language)}
                  className={`px-3 py-2 rounded-lg border cursor-pointer transition-colors ${
                    preferences.programming_languages.includes(language)
                      ? "border-indigo-600 bg-indigo-50 text-indigo-700"
                      : "border-gray-200 hover:border-indigo-300"
                  }`}
                >
                  {language}
                </div>
              ))}
            </div>
          </div>

          {/* Development Areas */}
          <div>
            <h2 className="text-xl font-semibold text-gray-800 mb-4">
              What development areas do you want to focus on?
            </h2>
            <div className="flex flex-wrap gap-3">
              {developmentAreaOptions.map((area) => (
                <div
                  key={area}
                  onClick={() => handleAreaToggle(area)}
                  className={`px-3 py-2 rounded-lg border cursor-pointer transition-colors ${
                    preferences.development_areas.includes(area)
                      ? "border-indigo-600 bg-indigo-50 text-indigo-700"
                      : "border-gray-200 hover:border-indigo-300"
                  }`}
                >
                  {area}
                </div>
              ))}
            </div>
          </div>

          <div className="pt-4">
            <button
              type="submit"
              disabled={submitting}
              className="w-full btn btn-primary py-3 text-lg"
            >
              {submitting ? "Saving..." : "Save Preferences"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Preferences;
