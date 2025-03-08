import React from "react";

const Dashboard: React.FC = () => {
  return (
    <div className="flex flex-col justify-center items-center h-screen w-screen">
      <h1>Dashboard</h1>
      <input
        type="text"
        placeholder="Enter chat message..."
        className=" px-4 h-12 w-[80%] border-2 border-indigo-400 rounded-md focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:inset-ring-2 focus:inset-ring-indigo-200"
      />
    </div>
  );
};

export default Dashboard;
