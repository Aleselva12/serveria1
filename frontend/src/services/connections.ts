import projectStatus from "../project-status.generated.json";

export const homeRoadmap = {
  ...projectStatus,
  categories: projectStatus.categories.map(category => ({
    ...category,
    goals: projectStatus.goals.filter(goal => goal.category === category.id),
  })),
};
