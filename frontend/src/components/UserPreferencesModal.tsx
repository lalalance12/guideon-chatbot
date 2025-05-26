import { useState, useEffect } from "react";
import { preferenceService, UserPreferences } from "../services/preferences";

interface UserPreferencesModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function UserPreferencesModal({
  isOpen,
  onClose,
}: UserPreferencesModalProps) {
  const [preferences, setPreferences] = useState<UserPreferences | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Programming languages and development areas options
  const programmingLanguagesOptions = [
    "JavaScript",
    "TypeScript",
    "Python",
    "Java",
    "C#",
    "C++",
    "Ruby",
    "Go",
    "PHP",
    "Swift",
  ];

  const developmentAreasOptions = [
    "Web Development",
    "Mobile Development",
    "Data Science",
    "DevOps",
    "Machine Learning",
    "Backend Development",
    "Frontend Development",
    "Cloud Computing",
    "Game Development",
    "Cybersecurity",
  ];

  useEffect(() => {
    if (isOpen) {
      fetchPreferences();
    }
  }, [isOpen]);
  const fetchPreferences = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await preferenceService.getPreferences();
      console.log("Fetched user preferences:", data);

      // Ensure programming_languages and development_areas are arrays
      const sanitizedData = {
        ...data,
        programming_languages: Array.isArray(data.programming_languages)
          ? data.programming_languages
          : [],
        development_areas: Array.isArray(data.development_areas)
          ? data.development_areas
          : [],
      };

      setPreferences(sanitizedData);
    } catch (err) {
      console.error("Failed to fetch preferences:", err);
      setError("Failed to load your preferences. Please try again.");
      // Set default values if unable to fetch
      setPreferences({
        course_level: "all",
        programming_languages: [],
        development_areas: [],
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!preferences) return;

    setSaving(true);
    setError(null);
    setSuccess(false);

    try {
      await preferenceService.updatePreferences(preferences);
      setSuccess(true);
      setTimeout(() => {
        onClose();
        setSuccess(false);
      }, 1500);
    } catch (err) {
      console.error("Failed to update preferences:", err);
      setError("Failed to save your preferences. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  const handleLevelChange = (level: UserPreferences["course_level"]) => {
    if (preferences) {
      setPreferences({ ...preferences, course_level: level });
    }
  };

  const handleProgrammingLanguageToggle = (language: string) => {
    if (!preferences) return;

    const updatedLanguages = preferences.programming_languages.includes(
      language
    )
      ? preferences.programming_languages.filter((lang) => lang !== language)
      : [...preferences.programming_languages, language];

    setPreferences({ ...preferences, programming_languages: updatedLanguages });
  };

  const handleDevelopmentAreaToggle = (area: string) => {
    if (!preferences) return;

    const updatedAreas = preferences.development_areas.includes(area)
      ? preferences.development_areas.filter((a) => a !== area)
      : [...preferences.development_areas, area];

    setPreferences({ ...preferences, development_areas: updatedAreas });
  };
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-white rounded-lg w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto shadow-xl">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-bold text-gray-800">
            Your Learning Preferences
          </h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700"
            aria-label="Close"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-6 w-6"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>{" "}
        {loading ? (
          <div className="flex flex-col items-center justify-center my-8">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600 mb-3"></div>
            <p className="text-gray-600">Loading your preferences...</p>
          </div>
        ) : (
          <>
            {error && (
              <div className="mb-4 p-3 bg-red-100 text-red-700 rounded-md">
                {error}
              </div>
            )}

            {success && (
              <div className="mb-4 p-3 bg-green-100 text-green-700 rounded-md">
                Preferences saved successfully!
              </div>
            )}

            <div className="space-y-6">
              {/* Course Level Section */}
              <div>
                <h3 className="text-md font-semibold text-gray-700 mb-3">
                  Preferred Course Level
                </h3>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {" "}
                  {(
                    ["beginner", "intermediate", "advanced", "all"] as const
                  ).map((level) => (
                    <button
                      key={level}
                      onClick={() => handleLevelChange(level)}
                      className={`py-2 px-3 rounded-md border transition-colors ${
                        preferences?.course_level === level
                          ? "bg-indigo-100 border-indigo-500 text-indigo-700 font-medium shadow-sm"
                          : "border-gray-300 hover:bg-gray-50 text-gray-700"
                      }`}
                    >
                      {level.charAt(0).toUpperCase() + level.slice(1)}
                    </button>
                  ))}
                </div>
              </div>

              {/* Programming Languages Section */}
              <div>
                <h3 className="text-md font-semibold text-gray-700 mb-3">
                  Programming Languages
                </h3>
                <div className="flex flex-wrap gap-2">
                  {" "}
                  {programmingLanguagesOptions.map((language) => (
                    <button
                      key={language}
                      onClick={() => handleProgrammingLanguageToggle(language)}
                      className={`py-1 px-3 rounded-full border text-sm transition-colors ${
                        preferences?.programming_languages.includes(language)
                          ? "bg-indigo-100 border-indigo-500 text-indigo-700 font-medium shadow-sm"
                          : "border-gray-300 hover:bg-gray-50 text-gray-700"
                      }`}
                    >
                      {language}
                    </button>
                  ))}
                </div>
              </div>

              {/* Development Areas Section */}
              <div>
                <h3 className="text-md font-semibold text-gray-700 mb-3">
                  Development Areas
                </h3>
                <div className="flex flex-wrap gap-2">
                  {" "}
                  {developmentAreasOptions.map((area) => (
                    <button
                      key={area}
                      onClick={() => handleDevelopmentAreaToggle(area)}
                      className={`py-1 px-3 rounded-full border text-sm transition-colors ${
                        preferences?.development_areas.includes(area)
                          ? "bg-indigo-100 border-indigo-500 text-indigo-700 font-medium shadow-sm"
                          : "border-gray-300 hover:bg-gray-50 text-gray-700"
                      }`}
                    >
                      {area}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-8">
              <button
                onClick={onClose}
                className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className={`px-4 py-2 rounded-md text-white transition-colors ${
                  saving
                    ? "bg-indigo-400 cursor-not-allowed"
                    : "bg-indigo-600 hover:bg-indigo-700"
                }`}
              >
                {saving ? "Saving..." : "Save Preferences"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
